# Defense-Eval Report

**Positions:** 55839

## Regret (primary)
| | mean | zero-regret |
|---|--:|--:|
| ours | 0.383 | 82.7% |
| current C++ | 0.356 | 84.7% |

## Exact-match-iso / Prime-match
| | exact-match | prime-match |
|---|--:|--:|
| ours | 82.7% | 88.7% |
| current C++ | 84.7% | 91.7% |

## Per-unit divergence (AI chumps/saves differently than humans)
| Unit | HP | Charge | Lifespan | ai-only chumped | human-only chumped | examples (ai-only / human-only) |
|---|--:|--:|--:|--:|--:|---|
| Engineer | 1 | - | - | 1571 | 7805 | ++olh-wraRD@t22, +8HlK-BZS0J@t21, +8HlK-BZS0J@t25, +8HlK-BZS0J@t31, +G7gY-4uhVt@t13 / +0Uwb-QeB+B@t14, +8HlK-BZS0J@t18, +8HlK-BZS0J@t22, +90KA-t9Ef4@t16, +982Y-PG+5w@t15 |
| Wall | 3 | - | - | 4367 | 1024 | +0Uwb-QeB+B@t14, +3@i+-0pBRr@t15, +3@i+-0pBRr@t16, +3@i+-0pBRr@t18, +3@i+-0pBRr@t19 / +FPif-Sa6pQ@t21, +OJZX-B+j7W@t17, +OJZX-B+j7W@t21, +by8B-0eCes@t23, +by8B-0eCes@t25 |
| Forcefield | 2 | - | - | 2559 | 129 | +MBWT-epO8W@t17, +MBWT-epO8W@t19, +MBWT-epO8W@t21, +OJZX-B+j7W@t17, +OJZX-B+j7W@t19 / +Xbxz-SHBcv@t24, +ZOfK-INjvt@t21, 0Q2Fa-P8f53@t19, 0Q2Fa-P8f53@t21, 16msF-5ZwRl@t21 |
| Rhino | 2 | 2 | - | 283 | 1468 | +PCrP-Yn2gQ@t18, 0q6WG-e2UZT@t14, 108nn-vyQwz@t44, 108nn-vyQwz@t46, 109E2-DeKJY@t26 / +3@i+-0pBRr@t19, +F8I5-Feri2@t19, +F8I5-Feri2@t21, +F8I5-Feri2@t22, +FPif-Sa6pQ@t23 |
| Nitrocybe | 1 | - | - | 1054 | 66 | +982Y-PG+5w@t15, +982Y-PG+5w@t21, +MBWT-epO8W@t16, +MBWT-epO8W@t18, +MBWT-epO8W@t20 / +MBWT-epO8W@t22, +OJZX-B+j7W@t23, 05O@2-yPQOy@t33, 1kKFk-UQpey@t18, 1kKFk-UQpey@t20 |
| Husk | 1 | - | - | 682 | 266 | +Scqa-20G0H@t18, 0DfyK-h3Mf8@t18, 0DfyK-h3Mf8@t20, 0QTrP-wb1pg@t21, 0QTrP-wb1pg@t25 / 0dnSu-yOgrW@t30, 1IbpY-TumET@t30, 2MiCj-harSA@t22, 2MiCj-harSA@t24, 2MiCj-harSA@t26 |
| Drone | 1 | - | - | 34 | 589 | 38bQH-Xnp@p@t20, 7lmMa-f7wpF@t27, 7yEQi-xSj9e@t34, 8a7x+-94@np@t33, BnRAJ-TBHF2@t38 / +cvBx-rRItc@t15, +laGq-7tK@V@t23, +tlHW-SQpvn@t22, +uH0p-iF9DE@t22, 0Gvpt-Uem7w@t25 |
| Protoplasm | 4 | - | - | 585 | 0 | +MNNI-vrJj4@t17, +MNNI-vrJj4@t19, +PCrP-Yn2gQ@t13, +cvBx-rRItc@t14, +cvBx-rRItc@t15 |
| Perforator | 2 | - | - | 24 | 555 | +sf5U-DoyDc@t24, 1MhFg-YKS3X@t22, 1VYbT-@M@OC@t36, 33Rkn-qowc5@t17, 6lesc-HqpF8@t23 / +3@i+-0pBRr@t15, +3@i+-0pBRr@t16, +3@i+-0pBRr@t18, +6nVE-wsiqX@t15, +a0Ss-rPM2U@t18 |
| Barrier | 1 | - | 1 | 8 | 516 | 0hF0J-YR6iK@t28, 1l6fu-yvt0d@t15, 5cgGl-bz3FX@t25, 7U@8t-q2spy@t32, 8RHmo-iMct5@t36 / +7Msl-Gmh41@t18, +7Msl-Gmh41@t24, +Aeyh-h4vXD@t21, +Aeyh-h4vXD@t26, +e+d7-dfBcy@t20 |
| Ossified Drone | 2 | - | - | 4 | 457 | 1droY-IRfD9@t15, RY3F1-MAvO+@t25, p3593-t5jiK@t31, p7i4U-JKTDC@t21 / +JQYi-VdEsx@t12, +JQYi-VdEsx@t20, +JQYi-VdEsx@t22, +JQYi-VdEsx@t23, +JQYi-VdEsx@t24 |
| Steelsplitter | 3 | - | - | 28 | 350 | 449@K-e9lXZ@t38, 66JQW-WEL82@t48, 8fnpT-fLTlo@t37, 9R39n-dnnFz@t26, A+wRV-Qdw8p@t27 / +7Msl-Gmh41@t19, +QzmS-VgORb@t33, +Scqa-20G0H@t18, +gBSl-WwL3c@t29, +z8tI-OucRU@t33 |
| Rhino | 2 | 1 | - | 318 | 45 | +FPif-Sa6pQ@t21, +ZOfK-INjvt@t26, +a0Ss-rPM2U@t13, +a0Ss-rPM2U@t18, +a0Ss-rPM2U@t20 / +j2P8-z6w12@t18, 16dhC-aztdO@t25, 2i9B8-yNkJQ@t18, 3gva5-9j5VL@t12, 3rMDk-rPexN@t22 |
| Infusion Grid | 4 | - | - | 269 | 91 | +JQYi-VdEsx@t20, +JQYi-VdEsx@t22, +JQYi-VdEsx@t23, +tlHW-SQpvn@t22, +uH0p-iF9DE@t22 / +MNNI-vrJj4@t17, +MNNI-vrJj4@t19, +Scqa-20G0H@t23, 0QTrP-wb1pg@t21, 0q6WG-e2UZT@t14 |
| Energy Matrix | 5 | - | - | 236 | 70 | +QzmS-VgORb@t33, +Xbxz-SHBcv@t24, +Zwpt-Su@Va@t18, +z8tI-OucRU@t30, 02MV2-IQ2Wd@t29 / 0xd1h-ss+Kb@t19, 1j1oV-SbQi3@t24, 1j1oV-SbQi3@t25, 1j1oV-SbQi3@t29, 1kKFk-UQpey@t22 |
| Rhino | 2 | - | - | 173 | 115 | +Scqa-20G0H@t23, +by8B-0eCes@t29, 0Q2Fa-P8f53@t23, 0hBxG-inUM@@t31, 0q6WG-e2UZT@t22 / +OJZX-B+j7W@t19, +OJZX-B+j7W@t21, 16oLY-CW5v2@t22, 2fb4D-wWLRi@t26, 2fb4D-wWLRi@t30 |
| Shiver Yeti | 2 | - | - | 255 | 16 | +e+d7-dfBcy@t33, +laGq-7tK@V@t20, +uH0p-iF9DE@t16, +uH0p-iF9DE@t20, 05PgJ-y3bE+@t24 / 0dnSu-yOgrW@t28, 2i9B8-yNkJQ@t22, 2i9B8-yNkJQ@t24, 5f6Fg-EOFYd@t22, 8uhCE-Flirk@t26 |
| Innervi Field | 3 | - | 3 | 198 | 43 | 0Q2Fa-P8f53@t15, 0uwuf-VgqV6@t21, 0uwuf-VgqV6@t23, 0uwuf-VgqV6@t27, 1tOV+-OYe9O@t17 / +j2P8-z6w12@t15, +j2P8-z6w12@t19, 7BbxV-37tIG@t23, 7a11+-fRVYH@t30, 8luZX-0SHPA@t21 |
| Feral Warden | 3 | - | - | 21 | 218 | 19VkT-tNkKn@t14, 19VkT-tNkKn@t16, 1tlRb-zFNlJ@t21, 5D6nO-9oyCi@t19, 5tYZn-db+Wc@t37 / +V3ey-CCx5X@t25, +wSiv-rbZ@N@t14, 1XdCT-DvgSZ@t18, 1XdCT-DvgSZ@t20, 1XdCT-DvgSZ@t21 |
| Plasmafier | 4 | - | - | 2 | 211 | A+wRV-Qdw8p@t23, SG5yH-uN@zS@t22 / +Zwpt-Su@Va@t18, 13pKq-5tXML@t27, 13pKq-5tXML@t29, 13pKq-5tXML@t31, 1jdZR-vwwdC@t26 |
| Xeno Guardian | 4 | - | - | 43 | 148 | 3gT9L-EWEft@t22, 6A6@p-IWTid@t22, 6A6@p-IWTid@t24, 6x2hp-4FzmK@t22, A8Qbr-ny2LA@t29 / +oxIv-Scr4c@t34, +z8tI-OucRU@t30, 0Dq46-u8A3k@t26, 11wt0-BMTlh@t24, 32Wc@-a@Px8@t27 |
| Photonic Fibroid | 2 | - | - | 93 | 96 | +ZOfK-INjvt@t28, 02rAI-fk0F9@t20, 0IDmx-CqECf@t20, 0qYjP-vqlhp@t25, 0qYjP-vqlhp@t27 / +ZOfK-INjvt@t19, +ZOfK-INjvt@t21, +ZOfK-INjvt@t23, +a0Ss-rPM2U@t29, 47Wh8-Chntj@t29 |
| Doomed Drone | 1 | - | 1 | 2 | 186 | 6T@cg-WRPlY@t22, YX6gZ-@n@Vc@t19 / +5S15-cfmxW@t14, +982Y-PG+5w@t19, +982Y-PG+5w@t20, +IsJh-fB7gy@t11, +IsJh-fB7gy@t21 |
| Cauterizer | 3 | - | - | 0 | 188 | +8HlK-BZS0J@t21, +8HlK-BZS0J@t25, +8HlK-BZS0J@t31, +uTXo-s@rv9@t20, 0MNHa-IcgD3@t20 |
| Corpus | 2 | 2 | - | 7 | 175 | E1stg-YyQfe@t15, Q@Co1-gqgi0@t27, SG5yH-uN@zS@t20, d0qVG-E8nE2@t21, dYp7R-bSU7d@t33 / 0Gvpt-Uem7w@t13, 0Gvpt-Uem7w@t19, 0Gvpt-Uem7w@t22, 0Gvpt-Uem7w@t23, 0oFZ0-n@57Y@t18 |
| Doomed Wall | 4 | - | 3 | 106 | 68 | 108nn-vyQwz@t26, 2pu58-MbXPp@t25, 31Rg8-Mw0+w@t30, 3b6dJ-ZOc26@t25, 4e+DE-FLrQ8@t20 / 0+nXK-dQG1x@t17, 108nn-vyQwz@t40, 19VkT-tNkKn@t16, 3cQmW-XyItQ@t15, 5jZc8-s9jaE@t25 |
| Electrovore | 2 | - | - | 2 | 162 | DPStf-tYYgJ@t15, oLWii-@dbyj@t22 / +PCrP-Yn2gQ@t18, +gBSl-WwL3c@t30, 0L2nT-BSCov@t18, 0ZOfp-X3hbh@t31, 0ZOfp-X3hbh@t33 |
| Grimbotch | 2 | - | 2 | 5 | 125 | QoutZ-PaTYu@t21, fkLmT-lSYgj@t32, kg1xO-1oyfO@t50, kqYkl-XFB7P@t33, zYdSy-DoYWN@t30 / +G7gY-4uhVt@t13, 05O@2-yPQOy@t33, 108nn-vyQwz@t19, 108nn-vyQwz@t23, 1Mh6@-B+twq@t24 |
| Borehole Patroller | 2 | - | - | 12 | 110 | 5jZc8-s9jaE@t19, A5e3E-4EXAK@t39, SG5yH-uN@zS@t29, ZvWL3-AKs8o@t35, eOMON-ubT9N@t21 / 02MV2-IQ2Wd@t28, 02MV2-IQ2Wd@t29, 0SnBR-7N2Bh@t24, 1kKFk-UQpey@t21, 1kKFk-UQpey@t23 |
| Doomed Wall | 4 | - | 2 | 53 | 57 | 108nn-vyQwz@t19, 31Rg8-Mw0+w@t28, 6bWu9-ryXeU@t35, 6cS6i-yYbi8@t24, 7lmMa-f7wpF@t20 / 19VkT-tNkKn@t14, 4LG+Z-rxc@C@t15, 5uD9j-Yn8hv@t18, @LV7c-Zx7Pn@t30, @PrB8-@Y5m3@t22 |

## Tie-break skew (corrective-term candidates)
| Unit | HP | Charge | Lifespan | vs Unit | HP | Charge | Lifespan | human lean | examples |
|---|--:|--:|--:|---|--:|--:|--:|---|---|
| Steelsplitter | 3 | - | - | Wall | 3 | - | - | Steelsplitter: 221, Wall: 31 | +7Msl-Gmh41@t15, +BdaQ-3IXtB@t13, +BdaQ-3IXtB@t15, +ZOfK-INjvt@t31, +j2P8-z6w12@t19 |
| Rhino | 2 | 2 | - | Wall | 3 | - | - | Wall: 246, Rhino: 2 | +F8I5-Feri2@t19, +FPif-Sa6pQ@t19, +OVLW-gn1IQ@t13, +OVLW-gn1IQ@t28, +OVLW-gn1IQ@t29 |
| Urban Sentry | 3 | - | - | Wall | 3 | - | - | Urban Sentry: 109, Wall: 8 | +e+d7-dfBcy@t12, 3Quy@-LostC@t25, 3uhSW-SR1bo@t13, 4fVLw-NI@tg@t26, 4u+iS-w4mSF@t13 |
| Borehole Patroller | 2 | - | - | Wall | 3 | - | - | Wall: 108, Borehole Patroller: 2 | +L5eO-onrlF@t17, 0B+de-elx65@t18, 2SAxl-KeOOP@t13, 2SAxl-KeOOP@t14, 2SAxl-KeOOP@t15 |
| Arka Sodara | 7 | - | - | Wall | 3 | - | - | Arka Sodara: 85, Wall: 1 | +7Msl-Gmh41@t18, 0Jnrk-zdymM@t15, 0Jnrk-zdymM@t18, 16dhC-aztdO@t26, 2+vpB-tUkWb@t19 |
| Centurion | 6 | - | - | Wall | 3 | - | - | Centurion: 84 | +BdaQ-3IXtB@t16, 05O@2-yPQOy@t17, 05O@2-yPQOy@t19, 05O@2-yPQOy@t21, 05O@2-yPQOy@t22 |
| Bombarder | 4 | - | - | Bombarder | 4 | 1 | - | Bombarder: 47, Bombarder: 18 | 3a3@N-9E6tt@t28, 5ZW7r-xsbgE@t23, 5ZW7r-xsbgE@t24, 7@ECb-9D3V6@t23, 7@ECb-9D3V6@t27 |
| Perforator | 2 | - | - | Wall | 3 | - | - | Wall: 58 | +a0Ss-rPM2U@t30, +a0Ss-rPM2U@t31, +kT0N-wfgM9@t25, 0tozj-yTcYb@t38, 8eiBe-q4GPV@t20 |
| Ossified Drone | 2 | - | - | Wall | 3 | - | - | Wall: 58 | +kT0N-wfgM9@t25, 3CBJ8-2G6f0@t22, 3CBJ8-2G6f0@t24, 3nTbE-BmRFy@t19, 5uMGX-Ej2vN@t22 |
| Infusion Grid | 4 | - | - | Wall | 3 | - | - | Infusion Grid: 54, Wall: 3 | 1CK11-rJWn5@t15, 31kqM-v49SH@t16, 40a+F-fZ+nW@t19, 43rbL-NrpW@@t23, 4b1RU-x+Ofb@t16 |
| Xeno Guardian | 4 | - | - | Wall | 3 | - | - | Xeno Guardian: 53, Wall: 2 | 3nTbE-BmRFy@t21, 48CSK-Y2EFg@t21, 5qqGu-vVZra@t28, 5qqGu-vVZra@t29, 6A6@p-IWTid@t21 |
| Energy Matrix | 5 | - | - | Wall | 3 | - | - | Energy Matrix: 52 | +MRIM-HrZLw@t16, +z8tI-OucRU@t16, +z8tI-OucRU@t22, 02MV2-IQ2Wd@t17, 02MV2-IQ2Wd@t25 |
| Bombarder | 4 | 1 | - | Wall | 3 | - | - | Bombarder: 47, Wall: 1 | +QtkV-gKLKS@t26, 14RU3-6e3Kj@t15, 5ZW7r-xsbgE@t23, 6+fWT-ZQRbg@t16, 6+fWT-ZQRbg@t24 |
| Doomed Wall | 4 | - | 2 | Doomed Wall | 4 | - | 3 | Doomed Wall: 34, Doomed Wall: 3 | BTVtG-guJSG@t25, FMOZF-Obgs@@t21, IAhbN-X4zI5@t23, IAhbN-X4zI5@t24, IAhbN-X4zI5@t26 |
| Plexo Cell | 4 | - | 1 | Wall | 3 | - | - | Plexo Cell: 34 | +7Msl-Gmh41@t20, 3J0iR-yPYX6@t22, 5n@iM-xZ2bG@t29, 6x2hp-4FzmK@t35, 6x2hp-4FzmK@t38 |
| Odin | 3 | - | - | Steelsplitter | 3 | - | - | Odin: 33, Steelsplitter: 1 | +Y0Sm-@b6CR@t15, 0MNHa-IcgD3@t20, 3M7Yx-2DDE+@t18, 3M7Yx-2DDE+@t20, @Z5dg-v3EnA@t20 |
| Rhino | 2 | - | - | Wall | 3 | - | - | Wall: 33, Rhino: 1 | 1CJ1m-M7nXh@t15, 3WaxE-KZdCF@t17, BXeip-az+t9@t23, BdZzF-herE2@t23, C2X2l-CCxhF@t16 |
| Bombarder | 4 | 2 | - | Wall | 3 | - | - | Bombarder: 32, Wall: 1 | 1W2nI-XASKl@t14, 1W2nI-XASKl@t16, 41lJ5-fvNND@t17, 4WRqn-z+2ZW@t21, 4e+DE-FLrQ8@t17 |
| Odin | 3 | - | - | Wall | 3 | - | - | Odin: 30, Wall: 1 | @4dR6-erfYG@t17, @Z5dg-v3EnA@t25, @Z5dg-v3EnA@t29, CBRiw-fIdHH@t22, EUPd7-FEXGD@t25 |
| Cauterizer | 3 | - | - | Wall | 3 | - | - | Cauterizer: 22, Wall: 5 | 1Oqzk-ih9QQ@t17, 1Oqzk-ih9QQ@t19, 4LG+Z-rxc@C@t16, 6kIs6-R8Hws@t24, 7Dls4-2UQsJ@t12 |
| Doomed Wall | 4 | - | 3 | Wall | 3 | - | - | Doomed Wall: 26 | 0+nXK-dQG1x@t37, 3b6dJ-ZOc26@t16, @57o1-7Vywr@t21, BTVtG-guJSG@t23, CRwcN-sJcMY@t15 |
| Bombarder | 4 | - | - | Wall | 3 | - | - | Bombarder: 25 | 41lJ5-fvNND@t23, 6FZ8h-0SsoV@t24, 7a11+-fRVYH@t24, Dyxfw-UI7PA@t21, FDzzp-8nKif@t18 |
| Valkyrion | 4 | - | - | Wall | 3 | - | - | Valkyrion: 23 | 4@8Dp-JFrHL@t15, 73URG-K3YQf@t17, 73URG-K3YQf@t21, Bznva-V@Uir@t18, D1VMv-IGTVV@t17 |
| Grimbotch | 2 | - | 1 | Wall | 3 | - | - | Grimbotch: 22 | 0hF0J-YR6iK@t28, 1Mh6@-B+twq@t23, 34HZx-YH67y@t22, 8Gfq0-f12x3@t33, Afkca-Vx5QS@t22 |
| Bombarder | 4 | 1 | - | Bombarder | 4 | 2 | - | Bombarder: 19, Bombarder: 3 | 14RU3-6e3Kj@t18, 36TdK-ILVmd@t21, 9zSqc-4y8uq@t18, @XPK8-KA4ux@t20, ANTOh-mSib@@t31 |
| Rhino | 2 | 1 | - | Wall | 3 | - | - | Wall: 21 | +FPif-Sa6pQ@t19, +Q@TX-R7MNM@t14, 0SnBR-7N2Bh@t18, 1rqkC-l4KtE@t12, 3jQw9-cCCFY@t16 |
| Steelsplitter | 3 | - | - | Urban Sentry | 3 | - | - | Urban Sentry: 18, Steelsplitter: 2 | 2pXpN-RBjRA@t20, 3uhSW-SR1bo@t12, 47Wh8-Chntj@t26, 4EVuD-xI8ci@t14, A3pWt-huQYb@t24 |
| Centurion | 6 | - | - | Energy Matrix | 5 | - | - | Centurion: 20 | 329i9-VnLOK@t22, 329i9-VnLOK@t23, 329i9-VnLOK@t25, 329i9-VnLOK@t27, 329i9-VnLOK@t29 |
| Mahar Rectifier | 5 | - | - | Wall | 3 | - | - | Mahar Rectifier: 9, Wall: 10 | @nBM5-HSdZP@t16, BfG5u-mJNSO@t15, BfG5u-mJNSO@t17, L+DIl-cSIE+@t25, LzB5L-i@y7l@t33 |
| Corpus | 2 | 2 | - | Wall | 3 | - | - | Wall: 18 | 41OXv-Ay6MI@t21, 41OXv-Ay6MI@t23, 5nGMJ-XqSb3@t16, 6G5rJ-2h7If@t22, 6mHV1-IE74U@t26 |

## Tripwire (value-sanity)
Negative min-loss positions (loss < -0.001): **0**

Suspicious (loss < -1): **0 suspicious (clean)**
