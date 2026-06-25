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
| Engineer | 1 | - | - | 1571 | 7805 | ++olh-wraRD@s284, +8HlK-BZS0J@s277, +8HlK-BZS0J@s394, +8HlK-BZS0J@s561, +G7gY-4uhVt@s164 / +0Uwb-QeB+B@s106, +8HlK-BZS0J@s176, +8HlK-BZS0J@s314, +90KA-t9Ef4@s122, +982Y-PG+5w@s194 |
| Wall | 3 | - | - | 4367 | 1024 | +0Uwb-QeB+B@s106, +3@i+-0pBRr@s221, +3@i+-0pBRr@s240, +3@i+-0pBRr@s290, +3@i+-0pBRr@s318 / +FPif-Sa6pQ@s212, +OJZX-B+j7W@s159, +OJZX-B+j7W@s229, +by8B-0eCes@s344, +by8B-0eCes@s407 |
| Forcefield | 2 | - | - | 2559 | 129 | +MBWT-epO8W@s188, +MBWT-epO8W@s231, +MBWT-epO8W@s288, +OJZX-B+j7W@s159, +OJZX-B+j7W@s197 / +Xbxz-SHBcv@s432, +ZOfK-INjvt@s232, 0Q2Fa-P8f53@s264, 0Q2Fa-P8f53@s311, 16msF-5ZwRl@s322 |
| Rhino | 2 | 2 | - | 283 | 1468 | +PCrP-Yn2gQ@s239, 0q6WG-e2UZT@s124, 108nn-vyQwz@s645, 108nn-vyQwz@s707, 109E2-DeKJY@s488 / +3@i+-0pBRr@s318, +F8I5-Feri2@s163, +F8I5-Feri2@s204, +F8I5-Feri2@s231, +FPif-Sa6pQ@s257 |
| Nitrocybe | 1 | - | - | 1054 | 66 | +982Y-PG+5w@s194, +982Y-PG+5w@s337, +MBWT-epO8W@s174, +MBWT-epO8W@s204, +MBWT-epO8W@s250 / +MBWT-epO8W@s310, +OJZX-B+j7W@s268, 05O@2-yPQOy@s509, 1kKFk-UQpey@s176, 1kKFk-UQpey@s218 |
| Husk | 1 | - | - | 682 | 266 | +Scqa-20G0H@s190, 0DfyK-h3Mf8@s231, 0DfyK-h3Mf8@s279, 0QTrP-wb1pg@s282, 0QTrP-wb1pg@s420 / 0dnSu-yOgrW@s407, 1IbpY-TumET@s409, 2MiCj-harSA@s406, 2MiCj-harSA@s510, 2MiCj-harSA@s575 |
| Drone | 1 | - | - | 34 | 589 | 38bQH-Xnp@p@s234, 7lmMa-f7wpF@s532, 7yEQi-xSj9e@s649, 8a7x+-94@np@s542, BnRAJ-TBHF2@s875 / +cvBx-rRItc@s181, +laGq-7tK@V@s301, +tlHW-SQpvn@s384, +uH0p-iF9DE@s475, 0Gvpt-Uem7w@s347 |
| Protoplasm | 4 | - | - | 585 | 0 | +MNNI-vrJj4@s151, +MNNI-vrJj4@s188, +PCrP-Yn2gQ@s148, +cvBx-rRItc@s167, +cvBx-rRItc@s181 |
| Perforator | 2 | - | - | 24 | 555 | +sf5U-DoyDc@s367, 1MhFg-YKS3X@s307, 1VYbT-@M@OC@s647, 33Rkn-qowc5@s260, 6lesc-HqpF8@s356 / +3@i+-0pBRr@s221, +3@i+-0pBRr@s240, +3@i+-0pBRr@s290, +6nVE-wsiqX@s106, +a0Ss-rPM2U@s295 |
| Barrier | 1 | - | 1 | 8 | 516 | 0hF0J-YR6iK@s501, 1l6fu-yvt0d@s158, 5cgGl-bz3FX@s327, 7U@8t-q2spy@s835, 8RHmo-iMct5@s676 / +7Msl-Gmh41@s186, +7Msl-Gmh41@s411, +Aeyh-h4vXD@s196, +Aeyh-h4vXD@s327, +e+d7-dfBcy@s272 |
| Ossified Drone | 2 | - | - | 4 | 457 | 1droY-IRfD9@s133, RY3F1-MAvO+@s396, p3593-t5jiK@s488, p7i4U-JKTDC@s278 / +JQYi-VdEsx@s102, +JQYi-VdEsx@s298, +JQYi-VdEsx@s404, +JQYi-VdEsx@s450, +JQYi-VdEsx@s480 |
| Steelsplitter | 3 | - | - | 28 | 350 | 449@K-e9lXZ@s668, 66JQW-WEL82@s1102, 8fnpT-fLTlo@s1013, 9R39n-dnnFz@s485, A+wRV-Qdw8p@s377 / +7Msl-Gmh41@s208, +QzmS-VgORb@s707, +Scqa-20G0H@s190, +gBSl-WwL3c@s411, +z8tI-OucRU@s609 |
| Rhino | 2 | 1 | - | 318 | 45 | +FPif-Sa6pQ@s212, +ZOfK-INjvt@s382, +a0Ss-rPM2U@s175, +a0Ss-rPM2U@s295, +a0Ss-rPM2U@s336 / +j2P8-z6w12@s254, 16dhC-aztdO@s302, 2i9B8-yNkJQ@s169, 3gva5-9j5VL@s120, 3rMDk-rPexN@s270 |
| Infusion Grid | 4 | - | - | 269 | 91 | +JQYi-VdEsx@s298, +JQYi-VdEsx@s404, +JQYi-VdEsx@s450, +tlHW-SQpvn@s384, +uH0p-iF9DE@s475 / +MNNI-vrJj4@s151, +MNNI-vrJj4@s188, +Scqa-20G0H@s342, 0QTrP-wb1pg@s282, 0q6WG-e2UZT@s124 |
| Energy Matrix | 5 | - | - | 236 | 70 | +QzmS-VgORb@s707, +Xbxz-SHBcv@s432, +Zwpt-Su@Va@s137, +z8tI-OucRU@s494, 02MV2-IQ2Wd@s539 / 0xd1h-ss+Kb@s252, 1j1oV-SbQi3@s296, 1j1oV-SbQi3@s313, 1j1oV-SbQi3@s390, 1kKFk-UQpey@s259 |
| Rhino | 2 | - | - | 173 | 115 | +Scqa-20G0H@s342, +by8B-0eCes@s548, 0Q2Fa-P8f53@s352, 0hBxG-inUM@@s457, 0q6WG-e2UZT@s318 / +OJZX-B+j7W@s197, +OJZX-B+j7W@s229, 16oLY-CW5v2@s308, 2fb4D-wWLRi@s354, 2fb4D-wWLRi@s435 |
| Shiver Yeti | 2 | - | - | 255 | 16 | +e+d7-dfBcy@s599, +laGq-7tK@V@s229, +uH0p-iF9DE@s270, +uH0p-iF9DE@s405, 05PgJ-y3bE+@s380 / 0dnSu-yOgrW@s349, 2i9B8-yNkJQ@s264, 2i9B8-yNkJQ@s328, 5f6Fg-EOFYd@s228, 8uhCE-Flirk@s436 |
| Innervi Field | 3 | - | 3 | 198 | 43 | 0Q2Fa-P8f53@s142, 0uwuf-VgqV6@s249, 0uwuf-VgqV6@s293, 0uwuf-VgqV6@s388, 1tOV+-OYe9O@s165 / +j2P8-z6w12@s146, +j2P8-z6w12@s290, 7BbxV-37tIG@s313, 7a11+-fRVYH@s573, 8luZX-0SHPA@s261 |
| Feral Warden | 3 | - | - | 21 | 218 | 19VkT-tNkKn@s120, 19VkT-tNkKn@s191, 1tlRb-zFNlJ@s264, 5D6nO-9oyCi@s355, 5tYZn-db+Wc@s639 / +V3ey-CCx5X@s392, +wSiv-rbZ@N@s117, 1XdCT-DvgSZ@s188, 1XdCT-DvgSZ@s266, 1XdCT-DvgSZ@s369 |
| Plasmafier | 4 | - | - | 2 | 211 | A+wRV-Qdw8p@s282, SG5yH-uN@zS@s281 / +Zwpt-Su@Va@s137, 13pKq-5tXML@s370, 13pKq-5tXML@s402, 13pKq-5tXML@s438, 1jdZR-vwwdC@s527 |
| Xeno Guardian | 4 | - | - | 43 | 148 | 3gT9L-EWEft@s349, 6A6@p-IWTid@s318, 6A6@p-IWTid@s415, 6x2hp-4FzmK@s293, A8Qbr-ny2LA@s390 / +oxIv-Scr4c@s793, +z8tI-OucRU@s494, 0Dq46-u8A3k@s379, 11wt0-BMTlh@s297, 32Wc@-a@Px8@s741 |
| Photonic Fibroid | 2 | - | - | 93 | 96 | +ZOfK-INjvt@s466, 02rAI-fk0F9@s269, 0IDmx-CqECf@s263, 0qYjP-vqlhp@s385, 0qYjP-vqlhp@s437 / +ZOfK-INjvt@s193, +ZOfK-INjvt@s232, +ZOfK-INjvt@s307, +a0Ss-rPM2U@s631, 47Wh8-Chntj@s490 |
| Doomed Drone | 1 | - | 1 | 2 | 186 | 6T@cg-WRPlY@s307, YX6gZ-@n@Vc@s314 / +5S15-cfmxW@s203, +982Y-PG+5w@s299, +982Y-PG+5w@s314, +IsJh-fB7gy@s92, +IsJh-fB7gy@s296 |
| Cauterizer | 3 | - | - | 0 | 188 | +8HlK-BZS0J@s277, +8HlK-BZS0J@s394, +8HlK-BZS0J@s561, +uTXo-s@rv9@s256, 0MNHa-IcgD3@s255 |
| Corpus | 2 | 2 | - | 7 | 175 | E1stg-YyQfe@s174, Q@Co1-gqgi0@s367, SG5yH-uN@zS@s224, d0qVG-E8nE2@s188, dYp7R-bSU7d@s537 / 0Gvpt-Uem7w@s133, 0Gvpt-Uem7w@s213, 0Gvpt-Uem7w@s255, 0Gvpt-Uem7w@s289, 0oFZ0-n@57Y@s217 |
| Doomed Wall | 4 | - | 3 | 106 | 68 | 108nn-vyQwz@s283, 2pu58-MbXPp@s359, 31Rg8-Mw0+w@s356, 3b6dJ-ZOc26@s388, 4e+DE-FLrQ8@s219 / 0+nXK-dQG1x@s177, 108nn-vyQwz@s570, 19VkT-tNkKn@s191, 3cQmW-XyItQ@s135, 5jZc8-s9jaE@s325 |
| Electrovore | 2 | - | - | 2 | 162 | DPStf-tYYgJ@s130, oLWii-@dbyj@s328 / +PCrP-Yn2gQ@s239, +gBSl-WwL3c@s429, 0L2nT-BSCov@s229, 0ZOfp-X3hbh@s482, 0ZOfp-X3hbh@s502 |
| Grimbotch | 2 | - | 2 | 5 | 125 | QoutZ-PaTYu@s251, fkLmT-lSYgj@s618, kg1xO-1oyfO@s1149, kqYkl-XFB7P@s927, zYdSy-DoYWN@s750 / +G7gY-4uhVt@s164, 05O@2-yPQOy@s509, 108nn-vyQwz@s162, 108nn-vyQwz@s227, 1Mh6@-B+twq@s420 |
| Borehole Patroller | 2 | - | - | 12 | 110 | 5jZc8-s9jaE@s153, A5e3E-4EXAK@s657, SG5yH-uN@zS@s491, ZvWL3-AKs8o@s699, eOMON-ubT9N@s252 / 02MV2-IQ2Wd@s491, 02MV2-IQ2Wd@s539, 0SnBR-7N2Bh@s289, 1kKFk-UQpey@s235, 1kKFk-UQpey@s283 |
| Doomed Wall | 4 | - | 2 | 53 | 57 | 108nn-vyQwz@s162, 31Rg8-Mw0+w@s310, 6bWu9-ryXeU@s740, 6cS6i-yYbi8@s318, 7lmMa-f7wpF@s259 / 19VkT-tNkKn@s120, 4LG+Z-rxc@C@s117, 5uD9j-Yn8hv@s205, @LV7c-Zx7Pn@s465, @PrB8-@Y5m3@s296 |

## Tie-break skew (corrective-term candidates)
| Unit | HP | Charge | Lifespan | vs Unit | HP | Charge | Lifespan | human lean | examples |
|---|--:|--:|--:|---|--:|--:|--:|---|---|
| Steelsplitter | 3 | - | - | Wall | 3 | - | - | Steelsplitter: 221, Wall: 31 | +7Msl-Gmh41@s133, +BdaQ-3IXtB@s99, +BdaQ-3IXtB@s125, +ZOfK-INjvt@s536, +j2P8-z6w12@s290 |
| Rhino | 2 | 2 | - | Wall | 3 | - | - | Wall: 246, Rhino: 2 | +F8I5-Feri2@s163, +FPif-Sa6pQ@s175, +OVLW-gn1IQ@s92, +OVLW-gn1IQ@s508, +OVLW-gn1IQ@s525 |
| Urban Sentry | 3 | - | - | Wall | 3 | - | - | Urban Sentry: 109, Wall: 8 | +e+d7-dfBcy@s111, 3Quy@-LostC@s460, 3uhSW-SR1bo@s106, 4fVLw-NI@tg@s356, 4u+iS-w4mSF@s100 |
| Borehole Patroller | 2 | - | - | Wall | 3 | - | - | Wall: 108, Borehole Patroller: 2 | +L5eO-onrlF@s211, 0B+de-elx65@s178, 2SAxl-KeOOP@s160, 2SAxl-KeOOP@s181, 2SAxl-KeOOP@s197 |
| Arka Sodara | 7 | - | - | Wall | 3 | - | - | Arka Sodara: 85, Wall: 1 | +7Msl-Gmh41@s186, 0Jnrk-zdymM@s131, 0Jnrk-zdymM@s170, 16dhC-aztdO@s344, 2+vpB-tUkWb@s232 |
| Centurion | 6 | - | - | Wall | 3 | - | - | Centurion: 84 | +BdaQ-3IXtB@s138, 05O@2-yPQOy@s113, 05O@2-yPQOy@s152, 05O@2-yPQOy@s181, 05O@2-yPQOy@s190 |
| Bombarder | 4 | - | - | Bombarder | 4 | 1 | - | Bombarder: 47, Bombarder: 18 | 3a3@N-9E6tt@s514, 5ZW7r-xsbgE@s361, 5ZW7r-xsbgE@s378, 7@ECb-9D3V6@s512, 7@ECb-9D3V6@s610 |
| Perforator | 2 | - | - | Wall | 3 | - | - | Wall: 58 | +a0Ss-rPM2U@s653, +a0Ss-rPM2U@s675, +kT0N-wfgM9@s401, 0tozj-yTcYb@s721, 8eiBe-q4GPV@s217 |
| Ossified Drone | 2 | - | - | Wall | 3 | - | - | Wall: 58 | +kT0N-wfgM9@s401, 3CBJ8-2G6f0@s466, 3CBJ8-2G6f0@s533, 3nTbE-BmRFy@s305, 5uMGX-Ej2vN@s301 |
| Infusion Grid | 4 | - | - | Wall | 3 | - | - | Infusion Grid: 54, Wall: 3 | 1CK11-rJWn5@s181, 31kqM-v49SH@s166, 40a+F-fZ+nW@s216, 43rbL-NrpW@@s324, 4b1RU-x+Ofb@s128 |
| Xeno Guardian | 4 | - | - | Wall | 3 | - | - | Xeno Guardian: 53, Wall: 2 | 3nTbE-BmRFy@s357, 48CSK-Y2EFg@s256, 5qqGu-vVZra@s512, 5qqGu-vVZra@s545, 6A6@p-IWTid@s295 |
| Energy Matrix | 5 | - | - | Wall | 3 | - | - | Energy Matrix: 52 | +MRIM-HrZLw@s208, +z8tI-OucRU@s166, +z8tI-OucRU@s298, 02MV2-IQ2Wd@s159, 02MV2-IQ2Wd@s417 |
| Bombarder | 4 | 1 | - | Wall | 3 | - | - | Bombarder: 47, Wall: 1 | +QtkV-gKLKS@s333, 14RU3-6e3Kj@s163, 5ZW7r-xsbgE@s361, 6+fWT-ZQRbg@s122, 6+fWT-ZQRbg@s258 |
| Doomed Wall | 4 | - | 2 | Doomed Wall | 4 | - | 3 | Doomed Wall: 34, Doomed Wall: 3 | BTVtG-guJSG@s328, FMOZF-Obgs@@s301, IAhbN-X4zI5@s261, IAhbN-X4zI5@s295, IAhbN-X4zI5@s349 |
| Plexo Cell | 4 | - | 1 | Wall | 3 | - | - | Plexo Cell: 34 | +7Msl-Gmh41@s305, 3J0iR-yPYX6@s308, 5n@iM-xZ2bG@s364, 6x2hp-4FzmK@s730, 6x2hp-4FzmK@s831 |
| Odin | 3 | - | - | Steelsplitter | 3 | - | - | Odin: 33, Steelsplitter: 1 | +Y0Sm-@b6CR@s135, 0MNHa-IcgD3@s255, 3M7Yx-2DDE+@s138, 3M7Yx-2DDE+@s182, @Z5dg-v3EnA@s225 |
| Rhino | 2 | - | - | Wall | 3 | - | - | Wall: 33, Rhino: 1 | 1CJ1m-M7nXh@s184, 3WaxE-KZdCF@s193, BXeip-az+t9@s343, BdZzF-herE2@s242, C2X2l-CCxhF@s159 |
| Bombarder | 4 | 2 | - | Wall | 3 | - | - | Bombarder: 32, Wall: 1 | 1W2nI-XASKl@s113, 1W2nI-XASKl@s148, 41lJ5-fvNND@s179, 4WRqn-z+2ZW@s189, 4e+DE-FLrQ8@s163 |
| Odin | 3 | - | - | Wall | 3 | - | - | Odin: 30, Wall: 1 | @4dR6-erfYG@s163, @Z5dg-v3EnA@s399, @Z5dg-v3EnA@s546, CBRiw-fIdHH@s355, EUPd7-FEXGD@s252 |
| Cauterizer | 3 | - | - | Wall | 3 | - | - | Cauterizer: 22, Wall: 5 | 1Oqzk-ih9QQ@s173, 1Oqzk-ih9QQ@s203, 4LG+Z-rxc@C@s151, 6kIs6-R8Hws@s370, 7Dls4-2UQsJ@s91 |
| Doomed Wall | 4 | - | 3 | Wall | 3 | - | - | Doomed Wall: 26 | 0+nXK-dQG1x@s688, 3b6dJ-ZOc26@s141, @57o1-7Vywr@s284, BTVtG-guJSG@s264, CRwcN-sJcMY@s231 |
| Bombarder | 4 | - | - | Wall | 3 | - | - | Bombarder: 25 | 41lJ5-fvNND@s308, 6FZ8h-0SsoV@s292, 7a11+-fRVYH@s397, Dyxfw-UI7PA@s301, FDzzp-8nKif@s188 |
| Valkyrion | 4 | - | - | Wall | 3 | - | - | Valkyrion: 23 | 4@8Dp-JFrHL@s118, 73URG-K3YQf@s227, 73URG-K3YQf@s325, Bznva-V@Uir@s216, D1VMv-IGTVV@s196 |
| Grimbotch | 2 | - | 1 | Wall | 3 | - | - | Grimbotch: 22 | 0hF0J-YR6iK@s501, 1Mh6@-B+twq@s399, 34HZx-YH67y@s299, 8Gfq0-f12x3@s435, Afkca-Vx5QS@s329 |
| Bombarder | 4 | 1 | - | Bombarder | 4 | 2 | - | Bombarder: 19, Bombarder: 3 | 14RU3-6e3Kj@s238, 36TdK-ILVmd@s330, 9zSqc-4y8uq@s215, @XPK8-KA4ux@s186, ANTOh-mSib@@s519 |
| Rhino | 2 | 1 | - | Wall | 3 | - | - | Wall: 21 | +FPif-Sa6pQ@s175, +Q@TX-R7MNM@s138, 0SnBR-7N2Bh@s162, 1rqkC-l4KtE@s185, 3jQw9-cCCFY@s186 |
| Steelsplitter | 3 | - | - | Urban Sentry | 3 | - | - | Urban Sentry: 18, Steelsplitter: 2 | 2pXpN-RBjRA@s217, 3uhSW-SR1bo@s88, 47Wh8-Chntj@s440, 4EVuD-xI8ci@s104, A3pWt-huQYb@s296 |
| Centurion | 6 | - | - | Energy Matrix | 5 | - | - | Centurion: 20 | 329i9-VnLOK@s273, 329i9-VnLOK@s298, 329i9-VnLOK@s348, 329i9-VnLOK@s374, 329i9-VnLOK@s400 |
| Mahar Rectifier | 5 | - | - | Wall | 3 | - | - | Mahar Rectifier: 9, Wall: 10 | @nBM5-HSdZP@s139, BfG5u-mJNSO@s163, BfG5u-mJNSO@s197, L+DIl-cSIE+@s364, LzB5L-i@y7l@s539 |
| Corpus | 2 | 2 | - | Wall | 3 | - | - | Wall: 18 | 41OXv-Ay6MI@s378, 41OXv-Ay6MI@s428, 5nGMJ-XqSb3@s148, 6G5rJ-2h7If@s237, 6mHV1-IE74U@s292 |

## Tripwire (value-sanity)
Negative min-loss positions (loss < -0.001): **0**

Suspicious (loss < -1): **0 suspicious (clean)**
