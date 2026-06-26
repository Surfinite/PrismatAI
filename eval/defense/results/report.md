# Defense-Eval Report

**Positions:** 55839

## Regret (primary)
| | mean | zero-regret |
|---|--:|--:|
| ours | 0.836 | 84.2% |
| current C++ | 0.356 | 84.7% |

## Exact-match-iso / Prime-match
| | exact-match | prime-match |
|---|--:|--:|
| ours | 84.2% | 92.2% |
| current C++ | 84.7% | 91.7% |

## Per-unit divergence (AI chumps/saves differently than humans)
| Unit | HP | Charge | Lifespan | ai-only chumped | human-only chumped | examples (ai-only / human-only) |
|---|--:|--:|--:|--:|--:|---|
| Engineer | 1 | - | - | 2110 | 5736 | ++olh-wraRD@s284, +8HlK-BZS0J@s277, +8HlK-BZS0J@s394, +8HlK-BZS0J@s561, +G7gY-4uhVt@s164 / +0Uwb-QeB+B@s106, +8HlK-BZS0J@s314, +982Y-PG+5w@s194, +IsJh-fB7gy@s140, +KtMW-xdjol@s106 |
| Wall | 3 | - | - | 1604 | 2213 | +0Uwb-QeB+B@s106, +8HlK-BZS0J@s314, +F8I5-Feri2@s163, +KtMW-xdjol@s106, +KtMW-xdjol@s170 / +5S15-cfmxW@s333, +5S15-cfmxW@s372, +6nVE-wsiqX@s141, +7dU7-CDcfu@s101, +7dU7-CDcfu@s161 |
| Forcefield | 2 | - | - | 2302 | 173 | +MBWT-epO8W@s231, +OJZX-B+j7W@s159, +OJZX-B+j7W@s197, +OJZX-B+j7W@s229, +OJZX-B+j7W@s268 / +Xbxz-SHBcv@s432, +ZOfK-INjvt@s232, 0Q2Fa-P8f53@s264, 0Q2Fa-P8f53@s311, 16msF-5ZwRl@s322 |
| Nitrocybe | 1 | - | - | 1048 | 57 | +982Y-PG+5w@s194, +982Y-PG+5w@s337, +MBWT-epO8W@s174, +MBWT-epO8W@s204, +MBWT-epO8W@s250 / +OJZX-B+j7W@s268, 05O@2-yPQOy@s509, 1kKFk-UQpey@s176, 1kKFk-UQpey@s218, 43i@1-zA27E@s129 |
| Rhino | 2 | 2 | - | 454 | 621 | +982Y-PG+5w@s337, +HGyu-zllmi@s75, +PCrP-Yn2gQ@s239, +kT0N-wfgM9@s464, 0q6WG-e2UZT@s124 / +F8I5-Feri2@s163, +OVLW-gn1IQ@s508, +PCrP-Yn2gQ@s148, +Q2yG-mFkoG@s282, +QtkV-gKLKS@s333 |
| Husk | 1 | - | - | 643 | 249 | +Scqa-20G0H@s190, 0DfyK-h3Mf8@s231, 0DfyK-h3Mf8@s279, 0QTrP-wb1pg@s282, 0QTrP-wb1pg@s420 / 1IbpY-TumET@s409, 2MiCj-harSA@s406, 2MiCj-harSA@s510, 2MiCj-harSA@s575, 2MiCj-harSA@s630 |
| Protoplasm | 4 | - | - | 579 | 0 | +MNNI-vrJj4@s151, +MNNI-vrJj4@s188, +PCrP-Yn2gQ@s148, +cvBx-rRItc@s167, +cvBx-rRItc@s181 |
| Drone | 1 | - | - | 47 | 531 | +fxCS-d8Z4b@s257, 38bQH-Xnp@p@s234, 3rR+y-ZYGIm@s278, 4Yaxv-9lTVh@s220, 7lmMa-f7wpF@s532 / +cvBx-rRItc@s181, +laGq-7tK@V@s301, +uH0p-iF9DE@s475, 0Gvpt-Uem7w@s347, 0Iwpr-aV5A+@s259 |
| Doomed Wall | 4 | - | 3 | 349 | 59 | +6nVE-wsiqX@s141, +7dU7-CDcfu@s101, 0+nXK-dQG1x@s454, 0+nXK-dQG1x@s526, 0+nXK-dQG1x@s583 / 108nn-vyQwz@s570, 19VkT-tNkKn@s191, 5jZc8-s9jaE@s325, 5uD9j-Yn8hv@s340, 8052a-5nP9R@s215 |
| Feral Warden | 3 | - | - | 329 | 57 | +EVZb-1oz+D@s134, +EVZb-1oz+D@s153, +EVZb-1oz+D@s166, +IsJh-fB7gy@s220, +V3ey-CCx5X@s349 / +V3ey-CCx5X@s392, 1XdCT-DvgSZ@s369, 6D0En-KxzLk@s197, A67wX-xwL3v@s584, B0urt-2W@FO@s138 |
| Rhino | 2 | 1 | - | 321 | 46 | +FPif-Sa6pQ@s212, +ZOfK-INjvt@s382, +a0Ss-rPM2U@s175, +a0Ss-rPM2U@s295, +a0Ss-rPM2U@s336 / +j2P8-z6w12@s254, 0+nXK-dQG1x@s583, 2i9B8-yNkJQ@s169, 2yJMo-iry3K@s260, 32zvL-Obr50@s164 |
| Perforator | 2 | - | - | 39 | 283 | +sf5U-DoyDc@s367, 1VYbT-@M@OC@s647, 33Rkn-qowc5@s260, 6lesc-HqpF8@s356, 8fnpT-fLTlo@s960 / +V3ey-CCx5X@s349, +a0Ss-rPM2U@s295, +a0Ss-rPM2U@s358, +a0Ss-rPM2U@s631, +a0Ss-rPM2U@s653 |
| Steelsplitter | 3 | - | - | 30 | 257 | 449@K-e9lXZ@s668, 4mwTo-djAkb@s278, 66JQW-WEL82@s1102, 8fnpT-fLTlo@s1013, 8pLZa-+GzIh@s309 / +7Msl-Gmh41@s208, +Scqa-20G0H@s190, +Y0Sm-@b6CR@s135, +gBSl-WwL3c@s411, +z8tI-OucRU@s609 |
| Rhino | 2 | - | - | 146 | 129 | +Scqa-20G0H@s342, 0Q2Fa-P8f53@s352, 0hBxG-inUM@@s403, 0hBxG-inUM@@s457, 0q6WG-e2UZT@s318 / +OJZX-B+j7W@s197, +OJZX-B+j7W@s229, +fxCS-d8Z4b@s257, 16oLY-CW5v2@s308, 2fb4D-wWLRi@s435 |
| Shiver Yeti | 2 | - | - | 258 | 17 | +e+d7-dfBcy@s599, +laGq-7tK@V@s229, +uH0p-iF9DE@s270, +uH0p-iF9DE@s405, 05PgJ-y3bE+@s380 / 2i9B8-yNkJQ@s264, 2i9B8-yNkJQ@s328, 5D6nO-9oyCi@s241, 8uhCE-Flirk@s436, T963i-aSheO@s120 |
| Ossified Drone | 2 | - | - | 20 | 230 | 1droY-IRfD9@s133, AmZ9b-vSt9n@s333, AmZ9b-vSt9n@s441, BcfkN-qXyew@s79, BcfkN-qXyew@s135 / +JQYi-VdEsx@s102, +JQYi-VdEsx@s298, +JQYi-VdEsx@s404, +JQYi-VdEsx@s480, +kT0N-wfgM9@s401 |
| Doomed Wall | 4 | - | 2 | 210 | 32 | +7dU7-CDcfu@s161, 0+nXK-dQG1x@s474, 0+nXK-dQG1x@s552, 0+nXK-dQG1x@s648, 0+nXK-dQG1x@s674 / 0dnSu-yOgrW@s192, 19VkT-tNkKn@s120, @LV7c-Zx7Pn@s465, A@Xlq-MWzQ4@s297, BTVtG-guJSG@s372 |
| Infusion Grid | 4 | - | - | 113 | 126 | +uH0p-iF9DE@s475, 0QTrP-wb1pg@s330, 0fC3f-dCxjw@s389, 178le-wWru3@s203, 1Fric-cDzZi@s790 / +MNNI-vrJj4@s151, +MNNI-vrJj4@s188, +Scqa-20G0H@s342, 0QTrP-wb1pg@s282, 0q6WG-e2UZT@s124 |
| Colossus | 8 | - | - | 193 | 0 | +ZOJE-bZgKL@s254, +uTXo-s@rv9@s256, +uTXo-s@rv9@s305, 02rAI-fk0F9@s243, 0B+de-elx65@s420 |
| Photonic Fibroid | 2 | - | - | 92 | 96 | +ZOfK-INjvt@s466, 02rAI-fk0F9@s269, 0IDmx-CqECf@s263, 0qYjP-vqlhp@s385, 0qYjP-vqlhp@s437 / +ZOfK-INjvt@s193, +ZOfK-INjvt@s232, +ZOfK-INjvt@s307, +a0Ss-rPM2U@s631, 47Wh8-Chntj@s490 |
| Borehole Patroller | 2 | - | - | 153 | 28 | 0B+de-elx65@s249, 0B+de-elx65@s677, 0ey3m-nSYlL@s180, 0ey3m-nSYlL@s226, 2ZLL2-f5jqp@s271 / 2ZLL2-f5jqp@s621, 4zsxG-yGNct@s187, 5ivgJ-Rzvmc@s440, @GmEQ-nGKEv@s367, D1VMv-IGTVV@s314 |
| Plasmafier | 4 | - | - | 74 | 92 | +IsJh-fB7gy@s140, +uH0p-iF9DE@s354, 0sGsQ-luEYM@s255, 16msF-5ZwRl@s139, 16msF-5ZwRl@s229 / 1jdZR-vwwdC@s527, 1jdZR-vwwdC@s661, 2ZLL2-f5jqp@s330, 2ZLL2-f5jqp@s621, 2ZLL2-f5jqp@s690 |
| Cauterizer | 3 | - | - | 0 | 154 | +8HlK-BZS0J@s277, +8HlK-BZS0J@s394, +8HlK-BZS0J@s561, +uTXo-s@rv9@s256, 0MNHa-IcgD3@s255 |
| Xeno Guardian | 4 | - | - | 39 | 112 | +z8tI-OucRU@s668, 3gT9L-EWEft@s349, 6A6@p-IWTid@s415, @LK6F-5p0re@s165, DUwUE-GlvUe@s292 / +oxIv-Scr4c@s793, 0Dq46-u8A3k@s379, 0bQLO-5Oljf@s227, 0bQLO-5Oljf@s648, 11wt0-BMTlh@s297 |
| Scorchilla | 3 | - | - | 147 | 0 | +7Msl-Gmh41@s208, +OVLW-gn1IQ@s394, +OVLW-gn1IQ@s598, +gsxV-hAQ2P@s134, +z8tI-OucRU@s177 |
| Energy Matrix | 5 | - | - | 41 | 99 | +Xbxz-SHBcv@s432, 2I0f9-HGPVk@s552, 329i9-VnLOK@s507, 5X0Oq-ti5bD@s338, 5X0Oq-ti5bD@s442 / +QzmS-VgORb@s635, +z8tI-OucRU@s668, 1j1oV-SbQi3@s390, 1kKFk-UQpey@s259, 5tYZn-db+Wc@s639 |
| Innervi Field | 3 | - | 3 | 38 | 94 | 3YDts-Qz+WY@s539, 5ROmk-ymDc2@s143, @6siE-U9U4d@s521, @Z5dg-v3EnA@s225, @Z5dg-v3EnA@s821 / +982Y-PG+5w@s337, +j2P8-z6w12@s146, +j2P8-z6w12@s290, 12aTn-haTIK@s175, 12aTn-haTIK@s351 |
| Barrier | 1 | - | 1 | 3 | 122 | 1l6fu-yvt0d@s158, @vl2d-SugiL@s102, lzpkz-PoKG@@s294 / +7Msl-Gmh41@s411, +MBWT-epO8W@s188, +e+d7-dfBcy@s272, 0L2nT-BSCov@s314, 0bQLO-5Oljf@s623 |
| Grimbotch | 2 | - | 2 | 5 | 118 | QoutZ-PaTYu@s251, fkLmT-lSYgj@s618, kg1xO-1oyfO@s1149, kqYkl-XFB7P@s927, zYdSy-DoYWN@s750 / +G7gY-4uhVt@s164, 05O@2-yPQOy@s509, 108nn-vyQwz@s162, 108nn-vyQwz@s227, 1Mh6@-B+twq@s420 |
| Electrovore | 2 | - | - | 7 | 104 | D+JRn-aUaMj@s361, DPStf-tYYgJ@s130, WHxKh-H9+ab@s146, oLWii-@dbyj@s328, xV1pT-JyFfu@s175 / +PCrP-Yn2gQ@s239, +gBSl-WwL3c@s429, 0L2nT-BSCov@s229, 1CJ1m-M7nXh@s87, 29aYI-MssNL@s237 |

## Tie-break skew (corrective-term candidates)
| Unit | HP | Charge | Lifespan | vs Unit | HP | Charge | Lifespan | human lean | examples |
|---|--:|--:|--:|---|--:|--:|--:|---|---|
| Steelsplitter | 3 | - | - | Wall | 3 | - | - | Steelsplitter: 189, Wall: 24 | +ZOfK-INjvt@s536, +j2P8-z6w12@s290, +j2P8-z6w12@s345, 05O@2-yPQOy@s229, 05O@2-yPQOy@s418 |
| Urban Sentry | 3 | - | - | Wall | 3 | - | - | Urban Sentry: 67, Wall: 4 | +e+d7-dfBcy@s111, 3Quy@-LostC@s460, 3uhSW-SR1bo@s106, 4fVLw-NI@tg@s356, 4u+iS-w4mSF@s200 |
| Bombarder | 4 | - | - | Bombarder | 4 | 1 | - | Bombarder: 41, Bombarder: 14 | 3a3@N-9E6tt@s514, 5ZW7r-xsbgE@s361, 5ZW7r-xsbgE@s378, 7@ECb-9D3V6@s512, 7@ECb-9D3V6@s610 |
| Odin | 3 | - | - | Wall | 3 | - | - | Odin: 28, Wall: 1 | @Z5dg-v3EnA@s399, @Z5dg-v3EnA@s546, CBRiw-fIdHH@s355, EUPd7-FEXGD@s252, EUPd7-FEXGD@s284 |
| Cauterizer | 3 | - | - | Wall | 3 | - | - | Cauterizer: 19, Wall: 3 | 1Oqzk-ih9QQ@s173, 1Oqzk-ih9QQ@s203, 6kIs6-R8Hws@s370, 7Dls4-2UQsJ@s91, 85dDc-VYMH0@s569 |
| Bombarder | 4 | 1 | - | Bombarder | 4 | 2 | - | Bombarder: 17, Bombarder: 2 | 14RU3-6e3Kj@s238, 36TdK-ILVmd@s330, 9zSqc-4y8uq@s215, @XPK8-KA4ux@s186, ANTOh-mSib@@s519 |
| Rhino | 2 | 1 | - | Rhino | 2 | 2 | - | Rhino: 15, Rhino: 2 | +h9AP-GWvuA@s97, NMlOs-P0a0u@s223, NQAR6-lCE8I@s184, NQAR6-lCE8I@s229, OzCCh-0AsgQ@s408 |
| Bombarder | 4 | - | - | Xeno Guardian | 4 | - | - | Xeno Guardian: 15, Bombarder: 1 | 6x2hp-4FzmK@s327, 8d9Wg-kVjiw@s292, GuMgC-nh2fa@s377, GuMgC-nh2fa@s420, eGiv3-XM5Ou@s356 |
| Steelsplitter | 3 | - | - | Urban Sentry | 3 | - | - | Urban Sentry: 13, Steelsplitter: 2 | 2pXpN-RBjRA@s217, 47Wh8-Chntj@s440, 4EVuD-xI8ci@s104, A3pWt-huQYb@s296, G5Dr5-VaPab@s171 |
| Rhino | 2 | 2 | - | Perforator | 2 | - | - | Rhino: 11, Perforator: 4 | 3gva5-9j5VL@s120, 7baPx-MDc0l@s152, @E1dI-pkcsJ@s141, @jzc0-ja3fH@s100, EYG@8-O@VUI@s406 |
| Rhino | 2 | - | - | Rhino | 2 | 2 | - | Rhino: 14 | 1AAy5-KPzwc@s327, 8piaA-EpnYN@s408, @b+rJ-nAwJA@s422, UME3b-+HqM8@s339, XVwyC-2+9NX@s309 |
| Odin | 3 | - | - | Steelsplitter | 3 | - | - | Odin: 13 | 0MNHa-IcgD3@s255, @Z5dg-v3EnA@s399, @Z5dg-v3EnA@s577, CBRiw-fIdHH@s393, LWTx+-FhUGD@s128 |
| Cauterizer | 3 | - | - | Urban Sentry | 3 | - | - | Urban Sentry: 11, Cauterizer: 2 | 16oLY-CW5v2@s289, 16oLY-CW5v2@s308, 16oLY-CW5v2@s330, 16oLY-CW5v2@s354, JvOFP-tBmFf@s296 |
| Borehole Patroller | 2 | - | - | Rhino | 2 | 2 | - | Borehole Patroller: 11, Rhino: 1 | 0B+de-elx65@s320, 2SAxl-KeOOP@s135, Bf+57-WAUlB@s130, CN7sI-Dnaaa@s395, CN7sI-Dnaaa@s567 |
| Rhino | 2 | 2 | - | Electrovore | 2 | - | - | Rhino: 2, Electrovore: 6 | @b+rJ-nAwJA@s286, BbZbb-JHq9D@s233, BbZbb-JHq9D@s305, MMW4n-uPk+Q@s81, YELaZ-Ez@SG@s75 |
| Doomed Wall | 4 | - | 3 | Wall | 3 | - | - | Doomed Wall: 8 | Dw1Y5-5aSwT@s237, FcFph-OMMfE@s578, aomHZ-35z1y@s354, aomHZ-35z1y@s434, hWk4Z-mh4N@@s220 |
| Doomed Wall | 4 | - | 3 | Urban Sentry | 3 | - | - | Doomed Wall: 8 | FcFph-OMMfE@s347, FcFph-OMMfE@s427, FcFph-OMMfE@s482, FcFph-OMMfE@s533, FcFph-OMMfE@s578 |
| Xeno Guardian | 4 | - | - | Valkyrion | 4 | - | - | Valkyrion: 6, Xeno Guardian: 1 | 4@8Dp-JFrHL@s494, Oy0sb-n@Pji@s366, SmUGf-AGWn5@s274, TC3Zq-Bep0w@s261, s8iAG-ZKFAL@s312 |
| Rhino | 2 | 2 | - | Protoplasm | 4 | - | - | Protoplasm: 6 | 419M@-GqXXa@s119, 419M@-GqXXa@s171, El+WD-mEMmD@s136, SVTjb-Tucc8@s163, czxz4-dZT8t@s339 |
| Cauterizer | 3 | - | - | Steelsplitter | 3 | - | - | Cauterizer: 5, Steelsplitter: 1 | 6kIs6-R8Hws@s370, EI2jy-hzcmG@s153, EI2jy-hzcmG@s168, LvRRO-JZeo+@s377, bBHZC-y36zb@s126 |
| Infusion Grid | 4 | - | - | Valkyrion | 4 | - | - | Valkyrion: 4, Infusion Grid: 1 | 1CK11-rJWn5@s126, 1CK11-rJWn5@s206, @k5x3-9o0xl@s541, Nr2eR-oDeEe@s135, Nr2eR-oDeEe@s212 |
| Rhino | 2 | 2 | - | Ossified Drone | 2 | - | - | Rhino: 5 | 3MxhE-tJC90@s298, CnnH3-I+Buo@s305, FK@Dw-DWO9l@s152, KD1qh-AQOI2@s237, W4NSB-mW@qH@s138 |
| Rhino | 2 | 2 | - | Photonic Fibroid | 2 | - | - | Rhino: 4, Photonic Fibroid: 1 | @b+rJ-nAwJA@s194, @b+rJ-nAwJA@s422, Lyy9E-zbcOl@s128, dMimY-ci9eB@s260, lyVgh-H4kgO@s112 |
| Doomed Wall | 4 | - | 3 | Steelsplitter | 3 | - | - | Doomed Wall: 5 | Dw1Y5-5aSwT@s237, aomHZ-35z1y@s354, aomHZ-35z1y@s434, rp0dt-Hwe2B@s484, uMILG-VdV7e@s294 |
| Rhino | 2 | - | - | Rhino | 2 | 1 | - | Rhino: 5 | EUsrH-KlNRI@s231, OzCCh-0AsgQ@s245, dXnLW-@g9gj@s373, kHHiq-7jjsE@s279, vi36e-RhYN+@s355 |
| Cauterizer | 3 | - | - | Doomed Wall | 4 | - | 3 | Doomed Wall: 5 | FcFph-OMMfE@s347, FcFph-OMMfE@s427, FcFph-OMMfE@s482, FcFph-OMMfE@s533, t5r9y-0Otif@s273 |
| Rhino | 2 | 1 | - | Protoplasm | 4 | - | - | Protoplasm: 4 | 419M@-GqXXa@s119, 419M@-GqXXa@s171, SVTjb-Tucc8@s163, og4t4-ITDeH@s323 |
| Protoplasm | 4 | - | - | Wall | 3 | - | - | Protoplasm: 4 | 5CSPZ-PaBkN@s163, C0RI6-npNGH@s297, EI2jy-hzcmG@s529, fAUiZ-PqImk@s261 |
| Electrovore | 2 | - | - | Perforator | 2 | - | - | Electrovore: 4 | 5fsre-GtKBB@s112, gr0oe-9htMb@s250, mSfsn-HBw7z@s220, rsyyN-hL6cF@s121 |
| Doomed Wall | 4 | - | 2 | Wall | 3 | - | - | Doomed Wall: 4 | BTVtG-guJSG@s245, OQNgI-ZvF+N@s313, aomHZ-35z1y@s181, wIzPx-Yz02l@s876 |

## Tripwire (value-sanity)
Negative min-loss positions (loss < -0.001): **0**

Suspicious (loss < -1): **0 suspicious (clean)**
