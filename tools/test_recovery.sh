#!/bin/bash
# test_recovery.sh — Launch a mirror instance from the current AMI,
# wait for all services to come up, report timing, then tear it down.
#
# Usage: bash tools/test_recovery.sh [--keep]
#   --keep  Don't terminate the instance (for debugging)
#
# NOTE: Does NOT steal the Elastic IP from production.
# Uses a temporary public IP for verification only.

set -euo pipefail

LAUNCH_TEMPLATE="lt-0b099958c1d0bce6a"
REGION="us-east-1"
SSH_KEY="$HOME/.ssh/prismata-spectator.pem"
SSH_OPTS="-i $SSH_KEY -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
KEEP=false

if [[ "${1:-}" == "--keep" ]]; then
    KEEP=true
fi

cleanup() {
    if [[ -n "${INSTANCE_ID:-}" ]] && [[ "$KEEP" == false ]]; then
        echo ""
        echo "=== Cleanup: terminating $INSTANCE_ID ==="
        aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" --region "$REGION" --output text 2>/dev/null | head -1
        echo "Instance terminating."
    fi
}
trap cleanup EXIT

timer() {
    echo "$(date +%s)"
}

elapsed() {
    local start=$1 end=$2
    echo "$((end - start))"
}

echo "========================================"
echo "  prismata.live Recovery Test"
echo "  $(date)"
echo "========================================"
echo ""

# Get current AMI from launch template
AMI_ID=$(aws ec2 describe-launch-template-versions \
    --launch-template-id "$LAUNCH_TEMPLATE" \
    --versions '$Default' \
    --region "$REGION" \
    --query 'LaunchTemplateVersions[0].LaunchTemplateData.ImageId' \
    --output text)
echo "AMI: $AMI_ID"

# Verify AMI is available
AMI_STATE=$(aws ec2 describe-images --image-ids "$AMI_ID" --region "$REGION" \
    --query 'Images[0].State' --output text 2>/dev/null)
if [[ "$AMI_STATE" != "available" ]]; then
    echo "ERROR: AMI $AMI_ID is '$AMI_STATE', not 'available'. Wait for it to finish."
    exit 1
fi

echo ""
echo "--- Phase 1: Launch instance ---"
T_TOTAL_START=$(timer)
T_LAUNCH_START=$(timer)

# Launch WITHOUT the EIP user-data (override with a no-op userdata)
# We want services to start but NOT steal the production EIP
USERDATA_TEST=$(echo '#!/bin/bash
echo "[$(date)] Recovery test instance — skipping EIP association"
# Restore latest DB from S3 (same as prod user-data minus EIP)
LATEST=$(aws s3 ls s3://prismata-live-backups-187740755172/daily/ 2>/dev/null | sort | tail -1 | awk "{print \$4}")
if [ -n "$LATEST" ]; then
    aws s3 cp "s3://prismata-live-backups-187740755172/daily/$LATEST" /tmp/latest_backup.db.gz 2>/dev/null
    gunzip -f /tmp/latest_backup.db.gz 2>/dev/null
    cp /tmp/latest_backup.db /opt/site/prismata_ladder.db 2>/dev/null
    chown ubuntu:ubuntu /opt/site/prismata_ladder.db 2>/dev/null
    rm -f /tmp/latest_backup.db
fi
# Restore ops config if missing
if [ ! -f /opt/site/ops/.env ]; then
    aws s3 cp s3://prismata-live-backups-187740755172/config/ops_config_backup.tar.gz /tmp/ 2>/dev/null
    tar xzf /tmp/ops_config_backup.tar.gz -C /opt/site/ 2>/dev/null
    rm -f /tmp/ops_config_backup.tar.gz
fi
# Restore credentials if missing
if [ ! -f /home/ubuntu/.prismata_multi_credentials ]; then
    aws s3 cp s3://prismata-live-backups-187740755172/config/prismata_multi_credentials /home/ubuntu/.prismata_multi_credentials 2>/dev/null
    chown ubuntu:ubuntu /home/ubuntu/.prismata_multi_credentials 2>/dev/null
    chmod 600 /home/ubuntu/.prismata_multi_credentials 2>/dev/null
fi
systemctl restart prismata-site prismata-spectator prismata-webhook nginx 2>/dev/null || true
' | base64 -w0)

INSTANCE_ID=$(aws ec2 run-instances \
    --launch-template "LaunchTemplateId=$LAUNCH_TEMPLATE,Version=\$Default" \
    --user-data "$USERDATA_TEST" \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=prismata-recovery-test},{Key=Purpose,Value=recovery-test}]" \
    --region "$REGION" \
    --query 'Instances[0].InstanceId' \
    --output text)

T_LAUNCH_END=$(timer)
echo "Instance: $INSTANCE_ID (launched in $(elapsed $T_LAUNCH_START $T_LAUNCH_END)s)"

echo ""
echo "--- Phase 2: Wait for instance running ---"
T_RUNNING_START=$(timer)

aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"

T_RUNNING_END=$(timer)
echo "Instance running ($(elapsed $T_RUNNING_START $T_RUNNING_END)s)"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region "$REGION" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo "Public IP: $PUBLIC_IP (temporary — NOT the Elastic IP)"

echo ""
echo "--- Phase 3: Wait for SSH ---"
T_SSH_START=$(timer)

for i in $(seq 1 60); do
    if ssh $SSH_OPTS ubuntu@"$PUBLIC_IP" "echo 'SSH OK'" 2>/dev/null; then
        break
    fi
    if [[ $i -eq 60 ]]; then
        echo "FAILED: SSH not available after 120s"
        exit 1
    fi
    sleep 2
done

T_SSH_END=$(timer)
echo "SSH ready ($(elapsed $T_SSH_START $T_SSH_END)s from instance running)"

echo ""
echo "--- Phase 4: Wait for services ---"
T_SERVICES_START=$(timer)

SERVICES_UP=false
for i in $(seq 1 60); do
    RESULT=$(ssh $SSH_OPTS ubuntu@"$PUBLIC_IP" '
        SITE=$(systemctl is-active prismata-site 2>/dev/null || echo "inactive")
        SPEC=$(systemctl is-active prismata-spectator 2>/dev/null || echo "inactive")
        HOOK=$(systemctl is-active prismata-webhook 2>/dev/null || echo "inactive")
        NGX=$(systemctl is-active nginx 2>/dev/null || echo "inactive")
        HTTP="DOWN"
        curl -sf http://localhost:3000 > /dev/null 2>&1 && HTTP="OK"
        echo "$SITE|$SPEC|$HOOK|$NGX|$HTTP"
    ' 2>/dev/null || echo "SSH_FAIL")

    IFS='|' read -r SITE SPEC HOOK NGX HTTP <<< "$RESULT"

    if [[ "$SITE" == "active" && "$SPEC" == "active" && "$HOOK" == "active" && "$NGX" == "active" && "$HTTP" == "OK" ]]; then
        SERVICES_UP=true
        break
    fi

    if [[ $((i % 5)) -eq 0 ]]; then
        echo "  Waiting... site=$SITE spectator=$SPEC webhook=$HOOK nginx=$NGX http=$HTTP"
    fi
    sleep 2
done

T_SERVICES_END=$(timer)

if [[ "$SERVICES_UP" == true ]]; then
    echo "All services UP ($(elapsed $T_SERVICES_START $T_SERVICES_END)s from SSH ready)"
else
    echo "WARNING: Not all services came up after 120s"
    echo "  site=$SITE spectator=$SPEC webhook=$HOOK nginx=$NGX http=$HTTP"
fi

echo ""
echo "--- Phase 5: Verify data ---"
T_DATA_START=$(timer)

ssh $SSH_OPTS ubuntu@"$PUBLIC_IP" '
    echo "DB size: $(du -h /opt/site/prismata_ladder.db 2>/dev/null | cut -f1 || echo MISSING)"
    echo "DB tables: $(sqlite3 /opt/site/prismata_ladder.db "SELECT count(*) FROM sqlite_master WHERE type=\"table\";" 2>/dev/null || echo FAILED)"
    echo "Games: $(sqlite3 /opt/site/prismata_ladder.db "SELECT count(*) FROM games;" 2>/dev/null || echo FAILED)"
    echo "Ops scripts: $(ls /opt/site/ops/*.sh 2>/dev/null | wc -l) files"
    echo "Credentials: $(test -f /home/ubuntu/.prismata_multi_credentials && echo OK || echo MISSING)"
    echo "Disk: $(df -h / | tail -1 | awk "{print \$5, \$4, \"free\"}")"
' 2>/dev/null

T_DATA_END=$(timer)

T_TOTAL_END=$(timer)

echo ""
echo "========================================"
echo "  RECOVERY TEST RESULTS"
echo "========================================"
echo ""
echo "  Launch → Running:    $(elapsed $T_LAUNCH_START $T_RUNNING_END)s"
echo "  Running → SSH:       $(elapsed $T_RUNNING_START $T_SSH_END)s"
echo "  SSH → Services UP:   $(elapsed $T_SSH_START $T_SERVICES_END)s"
echo "  ────────────────────────────"
echo "  TOTAL boot-to-live:  $(elapsed $T_TOTAL_START $T_SERVICES_END)s"
echo ""
echo "  Services: site=$SITE spectator=$SPEC webhook=$HOOK nginx=$NGX http=$HTTP"
echo "  Instance: $INSTANCE_ID ($PUBLIC_IP)"
echo ""

if [[ "$KEEP" == true ]]; then
    echo "  --keep flag set. Instance NOT terminated."
    echo "  SSH: ssh $SSH_OPTS ubuntu@$PUBLIC_IP"
    echo "  Terminate manually: aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION"
    trap - EXIT
else
    echo "  Terminating test instance..."
fi
