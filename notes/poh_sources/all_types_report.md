# POH lookup report, all 20 types (agent report, 2026-10-02)

Raw report from the lookup agents. Values are transcribed into reference/poh_types.csv.

## Max demonstrated crosswind, approach speed and VSO by type (POH/AFM sourced)

Every value below comes from a document that was opened, either by me or by one of three helper agents I ran in parallel. The agents quoted the exact phrase and page for each value, and many tables were checked against the rendered page image. Demonstrated crosswind is "not limiting" wherever the POH says so (all Cessna Section 5 charts, all Cirrus POHs, Saratoga II HP, Seneca V, Archer III G1000, M20R, Bonanza 2002 POH).

Column notes:
- **Approach** is the POH normal final-approach speed with landing flaps, in KIAS unless marked. Where the POH gives a range, the range is shown as printed.
- **VSO** is in KIAS. The basis is the Section 5 stall table (max weight, forward CG, 0° bank), the bottom of the Section 2 white arc, or the Section 4 "gross weight stalling speed" sentence, as noted.
- MPH conversions use 1 MPH = 0.869 kt.
- Sources are numbered S1 to S77, with URLs after the table. Q is source quality (1, 2 or 3).

| ICAO | Model / POH (weight) | Xwind kt | Approach KIAS | VSO KIAS | Src | Q | Notes (pages, basis) |
|---|---|---|---|---|---|---|---|
| P28A | PA-28-161 Warrior II, VB-1180 (1982, 2325 lb) | 17 | 63 (flaps 40°) | 44 | S1 | 1 | p.4-2. VSO from Sec 4 stall sentence. White arc 44-103. |
| P28A | PA-28-161 Warrior, 2440 lb (training checklist) | 17 | n/f | n/f | S2 | 2 | Checklist only. |
| P28A | PA-28-181 Archer II, VB-790 (1976) | 17 | 66 (40°) | 49 | S3 | 1 | p.4-1 and placard "DEMONSTRATED CROSS WIND COMPONENT - 17 KTS". VSO from Sec 4 sentence. |
| P28A | PA-28-181 Archer III, VB-1611 (1995, 2550 lb) | 17 | 66 (40°) | 45 | S4 | 1 | p.4-2. Sec 3 "2550 lbs (Full Flaps) 45 KIAS". |
| P28A | PA-28-181 Archer III G1000, VB-2749 (2017) | 17 | 66 (40°) | 45 | S5 | 1 | Placard says crosswind values are NOT limitations. |
| P28A | PA-28-180 Cherokee 180, 1973 Owner's Handbook (2450 lb) | not published | 85 MPH flaps up, minus 3 MPH per flap notch | 61 MPH CAS (53 kt) | S6 | 1 | No crosswind figure in the manual. |
| P28A | PA-28-180 Cherokee Archer 1974-75, AFM VB-558 | not found | n/f | 61 MPH CAS (53 kt) | S7 | 1 | OCR of the limitations and placard pages found no figure. White arc 61-115 MPH. |
| P28A | PA-28-151 Warrior (1974-77) | not found | n/f | n/f | - | - | Only a scanned copy with no text was available. |
| P28A | PA-28-140 Cherokee Cruiser, AFM VB-546 (1973, rev 1979, 2150 lb) | not published | 85 MPH flaps up, minus 3 MPH per notch | 55 MPH (48 kt) | S8, S9 | 1 | No placard. The older Cherokee 140 Owner's Handbook (S9) has no figure either. |
| C172 | 172S, Information Manual Rev 5 (2550 lb) | 15 | 60-70 (30°) | 40 | S10, S11 | 1 | p.4-5. Stall table 40 KIAS / 48 KCAS. White arc 40-85. |
| C172 | 172R, 1996 POH (2450 lb) | 15 | 60-70 (30°) | 33 | S12 | 1 | p.4-5. Stall table 33/47 KCAS. White arc 33-85. |
| C172 | 172P, 1981 POH (2400 lb) | 15 | 60-70 (30°) | 33 | S13 | 1 | Stall table. A 1985 copy also gives 15. |
| C172 | 172N, 1979 POH (2300 lb) | 15 | 55-65 (40°) | 41 | S14 | 1 | p.4-3. White arc 41-85. |
| C172 | 172M, 1976 POH (2300 lb) | 15 | 55-65 (40°) | 41 | S15 | 1 | Stall table and white arc agree. The 1975 owner's manual (S16) says "direct crosswinds of 15 knots can be handled with safety". |
| SR22 | SR22 G1-G3 analog/Avidyne, P/N 13772-001 (S/N 0002-2978 etc., 3400 lb) | 20 | 80-85 (flaps 100%), VREF 77 | 61 | S17 | 1 | Stall table 61/59 KCAS. White arc 59-104. |
| SR22 | SR22 Perspective, 13772-002 Reissue A (S/N 2979, 2992, 3002, 3026+, 3400 lb) | 20 | 80-85, VREF 77 | 62 | S18 | 1 | Stall table 62/60 KCAS. White arc 62-104. |
| SR22 | SR22 3600 lb, 13772-004 (Feb 2013, G5) | 21 | n/f | n/f | S19 | 1 | Only the Sec 4 crosswind text was extracted. |
| SR22 | SR22 G6, 13772-006 (S/N 4433+, 3600 lb) | 21 | 80-85, VREF 79 | 64 | S20 | 1 | Stall table 64/61 KCAS. White arc 64-110. |
| S22T | SR22T, 13772-005 (S/N 0442+, 3600 lb) | 21 | 80-85, VREF 79 | 64 | S21 | 1 | Stall table. White arc 64-110. |
| S22T | SR22T G7, AFM 44767-001 | 21 | 80-85 | 64 | S22 | 1 | White arc. |
| SR20 | SR20 analog/Avidyne, 11934-003 (S/N 1268+, 3000 lb) | 21 in Sec 4, 20 in Sec 5 | 75 (100%) | 56 | S23 | 1 | The POH contradicts itself. White arc 56-100. |
| SR20 | SR20 with G3 wing, supplement 11934-S37 (S/N 1878, 1886+, 3050 lb) | 20 | 78 | 61 | S23 | 1 | White arc 61-104. |
| SR20 | SR20 G6, 11934-005 (S/N 2220, 2339+, 3150 lb) | 20 | 78 | 62 | S24 | 1 | White arc 62-110. Stall table about 62. |
| SR20 | SR20 G7, AFM 44763-001 | 20 | 78 | 62 | S25 | 1 | White arc. |
| C182 | 182T, POH Apr 2001 (3100 lb) | 15 | 60-70 (full) | 41 | S26, S27 | 1 | POH p.5-14 note. Approach from the Cessna 182T NAV III Pilot's Checklist. Stall table 41/50 KCAS. |
| C182 | 182Q, 1977 POH (2950 lb) | T/O 20, landing 15 | 60-70 (40°) | 45 | S28 | 1 | White arc 45-95. |
| C182 | 182P, 1976 POH (2950 lb) | T/O 20, landing 15 | 60-70 (40°) | 48 | S29 | 1 | Page image checked. White arc 48-95. |
| P28R | PA-28R-180, Owner's Handbook | not published | n/f | n/f | S30 | 1 | OCR found no figure. |
| P28R | PA-28R-200, Owner's Handbook (S/N 28R-35001 to 35392) | not published | about 90 MPH (78 kt), flaps and gear down | 64 MPH (56 kt) | S31 | 1 | |
| P28R | PA-28R-200 Arrow II, AFM VB-560 (1973) | 20 MPH (17.4 kt) | 90 MPH (78 kt), full flaps | 64 MPH CAS (56 kt) | S32, S33 | 1 (approach Q2) | Placard "DEMONSTRATED CROSSWIND COMPONENT - 20 MPH". Approach from a university checklist (S33). |
| P28R | PA-28R-201 Arrow, VB-1365 (1988, S/N 2837001+) | 17 | 75 (40°) | 55 | S36 | 1 | p.4-2. VSO from Sec 4 sentence. White arc 55-103 (OCR). |
| P28R | PA-28R-201 Arrow, VB-1612 (1995+) | 17 | n/f | n/f | S37 | 2 | University packet and SOP only. |
| P28R | PA-28R-201 Arrow III (1977-78) | not found | n/f | n/f | - | - | POH only on Scribd, which was blocked. |
| (ref) | PA-28R-201T Turbo Arrow III, VB-800. PA-28RT-201 Arrow IV, VB-1130 | 17 / 17 | 75 / 74 | 56 / 53 | S34, S35 | 1 | These may be filed under P28T rather than P28R. |
| C150 | 150M, 1977 POH (1600 lb) | 13 | 50-60 (40°) | 42 | S38 | 1 | p.4-3. White arc 42-85. |
| C150 | 150L, 1974 owner's manual | not published | 60-70 MPH (52-61 kt), flaps down | 48 MPH CAS (42 kt) | S39 | 1 | The 1971 150L manual also has no figure. White arc 49-100 MPH CAS. |
| C150 | 150G, 1967 owner's manual | not published | 60-70 MPH, flaps down | 48 MPH CAS (42 kt) | S40 | 1 | Flaps-down 40 MPH IAS = 49 MPH CAS, so the IAS stall reads lower. |
| C150 | 150F (1966) | not found | n/f | n/f | - | - | Manual not opened. |
| C152 | 152, 1978 POH Change 2 (1670 lb) | 12 | 55-65 (30°) | 35 | S41 | 1 | The 1979 POH also gives 12. Stall table 35/43 KCAS. |
| AA5 | AA-5A Cheetah, 1977-79 POH | 16 | 65 (flaps DN) | 53 | S42 | 1 | Placard and p.4-3. White arc 53-104. |
| AA5 | AA-5B Tiger, 1977-79 POH | 16 | 69 (flaps DN, p.4-3 list) | 53 | S43 | 1 | The amplified Sec 4 text says 65 KIAS. |
| M20P | M20J 1977-78, POH 1221 Rev D | 12 MPH, given by POH as 11 kt | 71 | 55 | S44 | 1 | Stall table at 2740 lb. |
| M20P | M20J S/N 24-3000+, POH 1233 Rev B (2740 lb) | 11 | 71 (full) | 54 | S45 | 1 | p.5-14 and 5-33. Stall table 54. White arc 55-115. |
| M20P | M20J 1996+, POH 3203 Rev B (2900 lb) | 11 on T/O and landing charts, 13 on xwind chart | 78 | 58 | S46 | 1 | The POH contradicts itself. |
| M20P | M20E, 1971 owner's manual and AFM | not published | 80 MPH (69.5 kt) | 57 MPH IAS (49 kt) | S47 | 1 | White arc 63 MPH CAS. |
| M20P | M20K 252, POH 1236 Rev B (2900 lb) | 12 | 75 | 59 | S48 | 1 | Stall table 59. White arc 56. |
| M20P | M20K 231 (1979-85) | 15 | n/f | 56 | S49 | 3 | Magazine only (AOPA Pilot). |
| M20P | M20R Ovation, POH 3600 G | 13 | 75 (33°, 3200 lb) | 59 | S50 | 1 | "NOT A LIMITATION". |
| M20P | M20R Ovation2 / Ovation 2 GX | 13 / 13 | 75 / 75 | 59 / 59 | S51, S52 | 1 | Ovation3 not opened. Encore not found. |
| BE36 | Bonanza 36/A36 E-1 to E-926, 36-590002-19C3 (3600 lb) | 17 (20 mph) | 76 (flaps not stated) | 56 | S53 | 1 | White arc IAS 56-117 (56-123 for E-106+). |
| BE36 | A36 2002-06 Raytheon POH (E-2111+, inferred, 3650 lb) | 17 | 79 (30°) | 61 | S54 | 1 | White arc. |
| BE36 | G36 (E-3630, E-3636+, 36-590002-71A8) | 17 | 79 (30°) | 61 | S55 | 1 | White strip 61-124. |
| BE58 | Baron 58/58A TH-773 to TH-1395 (5400 lb) | 22 | 96 (flaps DN) | 74 | S56 | 1 | TH-1 to TH-772 also 22. White arc IAS 74-122. |
| BE58 | G58 (TH-2125+) | not found | n/f | 74 | S57 | 2 | FlightSafety training manual only. |
| PA32 | Cherokee Six 300, AFM VB-562 (1974-76) | 20 MPH (17.4 kt) | about 90 MPH (78 kt) | 63 MPH CAS (55 kt) | S58 | 1 | Placard. |
| PA32 | Cherokee Six 300 1977+, VB-830 (3400 lb) | 17 | 80 (40°) | 47 | S59 | 1 | White arc 47-109. |
| PA32 | PA-32-301 Saratoga (fixed gear) | 17 | n/f | 58 | S60 | 2 | AAIB report quoting the POH. |
| PA32 | PA-32-301T Turbo Saratoga, VB-1070 | 17 | 79 (40°) | 58 | S61 | 1 | White arc 58-112. |
| P32R | PA-32R-300 Lance, VB-840 (1976) | 17 | 75 (40°) | 52 | S62 | 1 | White arc 52-106. |
| P32R | PA-32R-301 Saratoga SP, VB-1080 | 17 | 79 | 57 | S63 | 1 | No title page in the copy. |
| P32R | PA-32R-301 Saratoga II HP, VB-1669 (S/N 3246088+) | 17 | 80 | 63 | S64 | 1 | "(Not a limitation)". |
| P32R | PA-32R-301T Saratoga II TC, VB-1975 | 17 | 80 | 63 | S65 | 1 | |
| C72R | 172RG Cutlass RG, 1980 POH (2650 lb) | 15 | 60-70 (30°) | 42 | S77 | 1 | Stall table 42/51 KCAS. For 172R aircraft filed as C72R, use the 172R row: 15 kt. |
| DA40 | DA40 Lycoming, AFM 6.01.01-E Rev 10 | 20 | 71 (LDG, 1150 kg), 73 at 1200 kg | 49 | S75 | 1 | 52 KIAS at 1200 kg. XLS coverage assumed, not verified. |
| DA40 | DA40 NG, AFM 6.01.15-E Rev 4 | 25 | 76 (1216 kg), 77 at 1280 kg | 60 | S76 | 1 | Stall table at 1310 kg. |
| PA34 | Seneca I PA-34-200, AFM VB-423 (1972) | 15 MPH (13.0 kt) | 95 MPH (82.6 kt) | 69 MPH CAS (60 kt) | S66 | 1 | A Purdue data sheet (Q2) says 12 MPH. |
| PA34 | Seneca II PA-34-200T, VB-850 | 17 | 83 (Sec 4.35 text), 79 in Sec 4.3 table | 61 | S67 | 1 | |
| PA34 | Seneca III PA-34-220T, VB-1110 (1981) | 17 | 90 | 64 | S68 | 1 | Seneca IV not found. |
| PA34 | Seneca V, VB-1649 / VB-1930 | 17 | 90 | 61 | S69 | 1 | "NOT limitations". |
| PA31 | PA-31 Navajo 310 hp, LK-1206 | 20 | 100 | 70 (63 KCAS) | S72 | 1 | Also stated in Sec 2. |
| PA31 | PA-31-325 Navajo C/R, LK-1207 | 20 | 95 | 70 | S73 | 1 | |
| PA31 | PA-31-350 Chieftain, LK-1208 | 20 | 110 approach, Vref 95 | 68 or 74 | S74 | 2 | Club checklist for an STC-modified aircraft. |
| PA44 | Seminole PA-44-180, VB-860 (1978) | 17 | 90 | 55 | S70 | 1 | |
| PA44 | Seminole G1000, VB-2636 (2016) | 17 | 75-85 (flaps down) | 55 | S71 | 1 | |

### Rows to double-check against a physical POH
1. **SR20 analog/Avidyne (11934-003):** 21 kt in Sec 4 but 20 kt in the Sec 5 note.
2. **SR22 G5 (13772-004):** 21 kt seen in the Sec 4 text only. The serial applicability was not confirmed.
3. **M20J 3203B:** 11 kt versus 13 kt in the same POH. The M20J 1221 approach MPH digit is illegible.
4. **Seneca I:** 15 MPH, and a Q2 data sheet conflicts with it.
5. **Seneca II:** two different approach speeds in the same POH.
6. **AA-5B:** two different approach speeds in the same POH (69 vs 65).
7. **182P and 182Q:** separate takeoff (20) and landing (15) values. Use 15 for landing.
8. **PA-31-350 Chieftain, G58 and PA-32-301:** no primary POH was opened. The PA-31-325 approach speed was matched from the text layer only.
9. **Cherokee Six VB-830:** the 47 KIAS white arc is low compared with the other PA-32s.
10. **Navajo VSO:** 70 KIAS vs 63 KCAS, a large position error near the stall.
11. **M20K 231:** magazine data only.
12. **Pre-1976 Piper and Cessna owner's-manual types:** PA-28-140, PA-28-180, PA-28R-180, early PA-28R-200, 150F/G/L and M20E all say "not published", and their speeds are in MPH, often CAS.
13. **Not found at all:**
    - PA-28-151
    - PA-28-180 Archer (1974-75) crosswind
    - Arrow III 1977-78
    - 150F
    - Seneca IV
    - M20K Encore
    - A36 E-927 to E-2110
    - SR22T before S/N 0442
14. **172N and 172P VSO:** the white arc was quoted from Sec 7 or the stall table, not Sec 2.

### Sources
- S1 https://basic6aviation.com/downloads/PA-28-161-POH.pdf
- S2 https://www.mga.edu/aviation/knight-flight/aircraft-information-procedures/docs/Warrior_Checklist.pdf
- S3 https://aacit.org/wp-content/uploads/2016/02/PA28-181-POH.pdf
- S4 https://fliegen.ch/pdf/afm/Archer_3/AFM_ArcherIII.pdf
- S5 https://spartanflightacademy.com/wp-content/uploads/2025/11/pa-28-g1000-POH.pdf
- S6 https://takeflightsandiego.com/assets/documents/1973%20PA-28-180.pdf
- S7 https://williamsonflyingclub.com/documents/aircraftHandbook180.pdf
- S8 https://www.takeflightsandiego.com/assets/documents/Cherokee140POH.PDF
- S9 https://data.ntsb.gov/Docket/Document/docBLOB?ID=19048562&FileExtension=pdf&FileName=PA-28-140+Perf+and+charts-Rel.pdf
- S10 https://www.befa.org/wp-content/uploads/2019/12/POH-Cessna-172S.pdf
- S11 https://data.ntsb.gov/Docket/Document/docBLOB?ID=40373691&FileExtension=.PDF&FileName=Cessna+172S+POH+%28excerpt%29-Master.PDF
- S12 http://www.ebzr.be/wp-content/uploads/2018/04/POH-C172R.pdf
- S13 https://www.lsvr.de/de/wp-content/uploads/2019/10/POH-Cessna-172-P-D-EKRM.pdf (also https://tx435.cap.gov/media/cms/C172PPOHwoSupplements_0A69C5AA130B9.pdf)
- S14 https://www.airbooks.dk/ewExternalFiles/Cessna_172N.pdf
- S15 https://s3.us-east-1.amazonaws.com/i.rockymountainflight.com/2/2021/09/Cessna-172M-POH.pdf
- S16 https://www.manualslib.com/manual/904210/Cessna-1975-172-Skyhawk.html?page=32
- S17 https://www.classicairaviation.com/wp-content/uploads/2013/10/SR22%20POH.pdf (applicability: https://data.ntsb.gov/Docket/Document/docBLOB?ID=40478396&FileExtension=.PDF&FileName=POH+Excerpt-Master.PDF)
- S18 https://tampabayaviation.com/wp-content/uploads/2023/01/SR22-POH.pdf
- S19 https://www.manualslib.com/manual/1068331/Cirrus-Sr22.html?page=134
- S20 https://inflightpilottraining.com/wp-content/uploads/2018/12/SR22-POH.pdf
- S21 https://befa.org/wp-content/uploads/2021/04/POH-Cirrus-SR22T-1.pdf
- S22 https://palomaraviation.com/pdf/sr22t-g7-poh.pdf
- S23 https://stpeteair.org/wp-content/uploads/cirrus-sr20-poh.pdf
- S24 https://atlasaviation.com/wp-content/uploads/2025/09/Cirrus-SR-20-G6-POH.pdf
- S25 https://mikegoulianaviation.com/wp-content/uploads/2025/04/SR20-G7-AFM.pdf
- S26 https://www.manualslib.com/manual/2892218/Cessna-182t-2001.html (pages 127-128)
- S27 https://www.dentoncap.org/uploads/checklist_cessna_182T.pdf
- S28 https://kerrville.cap.gov/media/cms/Cessna_182Q_864F8FC1979D4.pdf
- S29 https://cdn.hibuwebsites.com/4915530bf31f4385a4d7d16b6c7397f6/files/uploaded/skylane_182p.pdf
- S30 https://www.coyoteflight.com/resources/Aircraft_Manuals/Piper_PA-28R-180.pdf
- S31 https://data.ntsb.gov/Docket/Document/docBLOB?FileExtension=.PDF&FileName=Airplane+Owner%27s+Handbook+-+Excerpt-Master.PDF&ID=40459961
- S32 https://business.desu.edu/sites/business/files/document/11/arrow_200_chap_3_airplane_flight_manual.pdf
- S33 https://www.desu.edu/sites/business/files/document/11/dsu_arrow_-200.pdf
- S34 https://redarrow.dolmint.com/sites/default/files/book/POH_Arrow%20III.pdf
- S35 https://www.crosswindsaviation.com/wp-content/uploads/2018/10/Piper-Pa28rt201-Information-Manual.pdf
- S36 https://www.manualslib.com/manual/1638123/Arrow-Pa-28r-201.html (pages 25, 61, 85)
- S37 https://www.mga.edu/Aviation/knight-flight/aircraft-information-procedures/docs/Arrow_Systems_Packet.pdf
- S38 https://www.cpaviation.com/images/downloads/CESSNA_150_POH.pdf
- S39 https://www.manualslib.com/manual/2340524/Cessna-150-1974.html (pages 29, 46, 64)
- S40 https://www.manualslib.com/manual/1227208/Cessna-150g.html (pages 22, 26, 40)
- S41 https://longislandaviators.com/wp-content/uploads/2018/08/1978-Pilots-Operating-Handbook-Cessna-152.pdf (also https://www.cpaviation.com/images/downloads/Cessna%20152.pdf)
- S42 https://www.aya.org/resources/Documents/Aircraft%20Documents/AA-5/POH-AA5A.pdf
- S43 https://gpa.grumman-parts.com/wp-content/uploads/2017/08/AA-5B-POH-1977-78-79-SM.pdf
- S44 https://data.ntsb.gov/Docket/Document/docBLOB?FileExtension=pdf&FileName=M20J-POH-Rel.pdf&ID=16044052
- S45 https://www.mattbeyer.com/poh/Mooney-M20J-POH.pdf
- S46 http://mooney.free.fr/Manuels%20M20J/M20J/M20J_3203B.pdf
- S47 https://www.manualslib.com/manual/1345590/Chaparral-Mooney-M20e-1971.html
- S48 https://airsideaviation.ca/wp-content/uploads/2024/12/M20K_Handbook.pdf
- S49 https://www.aopa.org/news-and-media/all-news/1994/february/pilot/the-mooney-231
- S50 https://www.manualslib.com/manual/1168379/Mooney-M20r-Ovation.html
- S51 https://www.manualslib.com/manual/1911644/Mooney-M20r.html
- S52 https://docu.tips/documents/mooney-m20r-ovation-2-gx-pilot39s-operating-handbook-and-airplane-flight-manual-5c1314dc58edf
- S53 https://ee45728f75.clvaw-cdnwnd.com/fb27bf10296933013ab7cd99b9ff6972/200004879-7c9d47c9d6/bonanza-36--a36-serials-e-1-thru-e-926-complete-pilots-operating-handbook-compressed-3.pdf?ph=ee45728f75
- S54 https://malusflyers.com/Malus_Flyers/Malus_Flyers_files/A36%20POH.pdf
- S55 https://ee45728f75.clvaw-cdnwnd.com/fb27bf10296933013ab7cd99b9ff6972/200031587-ab46bab46c/G36%20POH-compressed.pdf?ph=ee45728f75
- S56 https://csobeech.com/files/B58-POH.pdf (TH-1 to TH-772: https://data.ntsb.gov/Docket/Document/docBLOB?ID=40389877&FileExtension=.PDF&FileName=Performance+Charts+from+POH%2FAFM-Master.PDF)
- S57 https://www.abul.org.br/biblioteca/182.pdf
- S58 https://jasonblair.net/wp-content/uploads/2015/06/Piper-PA-32-300POH.pdf
- S59 https://static1.squarespace.com/static/58ffb3aa725e25b57dcec02f/t/5b02e26e575d1f27890c7ac7/1526915720455/PIPER+761-632+5828.pdf
- S60 https://assets.publishing.service.gov.uk/media/5423026f40f0b61346000c0d/Piper_PA-32-301_Saratoga__G-BMDC_10-08.pdf
- S61 https://www.manualslib.com/manual/910005/Piper-Turbo-Saratoga-Pa-32-301t.html (pages 38, 74)
- S62 https://www.manualslib.com/manual/1923027/Piper-Aircraft-Corporation-Cherokee-Lance-Pa-32r-300.html
- S63 https://www.manualslib.com/manual/1566193/Piper-Aircraft-Corporation-Pa-32r-301t.html
- S64 https://stpeteair.org/wp-content/uploads/Saratoga-PA-32R-POH-with-TOC-.pdf
- S65 https://www.manualslib.com/manual/3642064/Piper-Saratoga-Ii-Tc.html
- S66 https://www.desu.edu/sites/business/files/document/11/seneca_200_chap_3_airplane_flight_manual.pdf and https://business.desu.edu/sites/business/files/document/11/seneca_200_chap_6_operating_instructions.pdf
- S67 https://www.racecityfo.com/wp-content/uploads/2021/08/pa34-200t-seneca-ii-poh.pdf
- S68 https://www.manualslib.com/manual/1104887/Piper-Seneca-Iii.html?page=80
- S69 https://www.skyservices-flightacademy.com/wp-content/uploads/2018/08/PA_34_220T_AFM.pdf (VB-1649: https://www.flyace.at/media/Handbuch_senecaV_FMW.pdf)
- S70 https://beachbanners.com/wp-content/uploads/2023/09/01-1979-PA44180-POH-AFM.pdf
- S71 https://www.se.edu/aviation/wp-content/uploads/sites/4/2022/08/SEMINOLE-PIM-2022-PA44-from-Piper.pdf
- S72 https://idoc.pub/documents/poh-piper-navajo-pa31-cc-kkg-on232kxojyl0
- S73 https://idoc.pub/documents/pa31-325-navajo-cr-pilots-operating-14309wmykj4j
- S74 https://www.hanscomaeroclub.com/wp-content/uploads/2024/05/Checklist-Navajo-v11-Hanscom.pdf
- S75 https://flygenesis.ca/wp-content/uploads/2023/12/DA40_POH.pdf
- S76 https://meddygair.co.uk/wp-content/uploads/2025/06/60115e-DA40-NG-AFM-r4-complete-POH.pdf
- S77 https://www.manualslib.com/manual/1106849/Cessna-1980-172rg-Cutlass.html (also https://flugschule-eichenberger.ch/AFM%20C172RG.pdf)

Downloaded PDFs are cached in /tmp/claude-1000/-home-dev/68775d47-92c5-40a5-bf60-58ff7bbaa6b7/scratchpad/pdf/.
