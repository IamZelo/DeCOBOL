       IDENTIFICATION DIVISION.                                         00010000
       PROGRAM-ID. PAYMENT.                                             00020007
       AUTHOR. ISURU, WONA & MALENE.                                    00030000
                                                                        00040000
      ***************************************************************   00050000
      * COBOL DB2 PROGRAM.                                          *   00060002
      * FUNCTION: READ FROM PAYMENT REPORT AND INSERT INTO PAYMENT  *   00061000
      * TABLE. A PART OF THE LENDWISE SYSTEM.                       *   00062002
      ***************************************************************   00070000
      *    ENVIRONMENT DIVISION.                                    *   00080000
      ***************************************************************   00090000
                                                                        00100000
       ENVIRONMENT DIVISION.                                            00110000
       INPUT-OUTPUT SECTION.                                            00120000
       FILE-CONTROL.                                                    00130000
           SELECT PAYIN ASSIGN TO INFILE                                00140000
               ORGANIZATION IS SEQUENTIAL                               00150000
               ACCESS MODE IS SEQUENTIAL                                00160000
               FILE STATUS IS FS-INFILE.                                00170000
                                                                        00180000
      ***************************************************************   00190000
      *    DATA DIVISION.                                           *   00200000
      ***************************************************************   00210000
                                                                        00220000
       DATA DIVISION.                                                   00230000
       FILE SECTION.                                                    00240000
                                                                        00250000
       FD PAYIN                                                         00260000
            RECORDING MODE F.                                           00270000
       01 DATA-RECORDS      PIC X(80).                                  00280005
                                                                        00290000
      ***************************************************************   00300000
      *    WORKING-STORAGE SECTION.                                 *   00310000
      ***************************************************************   00320000
                                                                        00330000
       WORKING-STORAGE SECTION.                                         00340000
      * INCLUDING COPYBOOK.                                             00341005
       COPY PAYRECIN.                                                   00342005
                                                                        00350005
      * INCLUDING SQLCA AND HOST VARIABLES.                             00360000
           EXEC SQL INCLUDE SQLCA   END-EXEC.                           00370000
           EXEC SQL INCLUDE PAYMENT END-EXEC.                           00380000
                                                                        00390000
      * FILE-STATUS.                                                    00410000
       01 FS-INFILE         PIC X(02).                                  00420000
       01 EOF               PIC X VALUE "N".                            00440003
                                                                        00450000
      * FOR CURRENT RECROD.                                             00451005
       01 READ-CNTR         PIC 9(03).                                  00452005
       01 OK-CNTR           PIC 9 VALUE 0.                              00453006
       01 ERR-CNTR          PIC 9 VALUE 0.                              00454006
       01 INS-CNTR          PIC 9 VALUE 0.                              00455006
       01 CHAR-CNTR         PIC 9(2).                                   00455106
                                                                        00456006
      * FOR FLAGING ERRORS.                                             00459105
       01 ERR-FLAG          PIC 9.                                      00459205
         88 PAYMENT-ID-ERR  VALUE 1.                                    00459305
         88 INVOICE-ID-ERR  VALUE 2.                                    00459405
         88 PAID-AMT-ERR    VALUE 3.                                    00459505
         88 PAID-DATE-ERR   VALUE 4.                                    00459605
                                                                        00459805
      * FOR CHECKING VALID PAID-DATE.                                   00460906
       01 WS-CURRENT-DATE.                                              00461006
         05 WS-DATE-YYYY    PIC X(4).                                   00461106
         05 WS-DATE-MM      PIC X(2).                                   00461206
         05 WS-DATE-DD      PIC X(2).                                   00461306
                                                                        00461406
       01 WS-DATE-GENERATED       PIC X(30).                            00461506
       01 WS-DATE-GENERATED-LINE  PIC X(50).                            00461606
       01 WS-DATE-FOR-CALC        PIC X(10).                            00461706
                                                                        00461806
      * FOR MOVING AND INSERTING DATA.                                  00462106
       01 MOVE-FLAG         PIC 9.                                      00462206
         88 PAYMENT-ID-R    VALUE 1.                                    00462306
         88 INVOICE-ID-R    VALUE 2.                                    00462406
         88 PAID-AMT-R      VALUE 3.                                    00462506
         88 PAID-DATE-R     VALUE 4.                                    00462606
                                                                        00463106
      * FOR DISPLAY IN SYSOUT.                                          00463805
       01 ERR-HEADER.                                                   00463905
         05 ERR-MESSAGE     PIC X(20) VALUE "ERROR MESSAGE:".           00464005
         05 ERR-P-ID        PIC X(15) VALUE "PAYMENT ID.".              00464105
         05 ERR-I-ID        PIC X(15) VALUE "INVOICE ID.".              00464205
         05 ERR-AMT         PIC X(15) VALUE "PAID AMOUNT.".             00464305
         05 ERR-DATE        PIC X(15) VALUE "PAID DATE.".               00464405
         05 ERR-UNKNOWN     PIC X(20) VALUE "UNKNOWN ERROR.".           00464506
                                                                        00464706
       01 ERR-REASON        PIC X(20).                                  00464806
         88 ERR-1           VALUE "NOT NUMERIC.".                       00464906
         88 ERR-2           VALUE "NONE ID.".                           00465006
         88 ERR-3           VALUE "EMPTY FIELD.".                       00465106
         88 ERR-4           VALUE "NEGATIVE VALUE.".                    00465206
         88 ERR-5           VALUE "INVALID CHAR.".                      00465306
         88 ERR-6           VALUE "INVALID DATE.".                      00465406
                                                                        00465505
                                                                        00465905
      ***************************************************************   00466000
      *    PROCEDURE DIVISION.                                      *   00470000
      ***************************************************************   00480000
                                                                        00490000
       PROCEDURE DIVISION.                                              00500000
                                                                        00510000
       000-MAIN SECTION.                                                00520000
                                                                        00530000
           DISPLAY "PAYMENT PROGRAM."                                   00540003
           DISPLAY "SQL CODE IS: " SQLCODE                              00550003
                                                                        00560000
           PERFORM 001-FETCH-DATE                                       00561006
           PERFORM 100-OPEN-FILE                                        00570000
           PERFORM UNTIL EOF = "Y"                                      00580001
              PERFORM 200-READ-RECORDS                                  00590001
                IF EOF = "N" THEN                                       00590106
                   PERFORM 210-ERROR-CONTROL                            00590206
                ELSE                                                    00600006
                   CONTINUE                                             00600106
                END-IF                                                  00600206
           END-PERFORM                                                  00601101
           PERFORM 500-CLOSE-FILE                                       00601206
                                                                        00602000
           STOP RUN.                                                    00603000
                                                                        00603106
                                                                        00603206
       001-FETCH-DATE SECTION.                                          00603306
      * FETCHING CURRENT DATE.                                          00603406
                                                                        00603506
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD                    00603606
                                                                        00603706
           STRING WS-DATE-DD "-" WS-DATE-MM "-" WS-DATE-YYYY            00603806
              DELIMITED BY SIZE                                         00603906
              INTO WS-DATE-GENERATED                                    00604006
                                                                        00604106
           STRING "GENERATED ON: " DELIMITED BY SIZE                    00604206
                  WS-DATE-GENERATED DELIMITED BY SIZE                   00605006
             INTO WS-DATE-GENERATED-LINE                                00606006
                                                                        00607006
           STRING WS-DATE-YYYY "-" WS-DATE-MM "-" WS-DATE-DD            00608006
             DELIMITED BY SIZE                                          00609006
             INTO WS-DATE-FOR-CALC                                      00609106
                                                                        00609206
           DISPLAY WS-DATE-FOR-CALC " DATE FOR CALC.".                  00609306
                                                                        00609406
                                                                        00609506
       100-OPEN-FILE SECTION.                                           00610000
      * OPENING THE INFILE.                                             00620000
                                                                        00621006
           OPEN INPUT PAYIN                                             00630000
           IF FS-INFILE NOT = "00"                                      00640003
              DISPLAY "ERROR OPENING THE INFILE PAYIN."                 00650000
              DISPLAY "FILE STATUS CODE: " FS-INFILE                    00660000
              STOP RUN                                                  00670000
           ELSE                                                         00680000
              CONTINUE                                                  00690000
           END-IF.                                                      00700001
                                                                        00710001
                                                                        00720000
       200-READ-RECORDS SECTION.                                        00730000
      * READING RECORDS FROM THE INFILE INTO THE VAR. COPYBOOK.         00740005
                                                                        00750000
           READ PAYIN INTO PAYMENT-DETAILS                              00760005
              AT END                                                    00770000
                 MOVE "Y" TO EOF                                        00780003
                 DISPLAY " "                                            00790000
                 DISPLAY "REACHED END OF FILE."                         00800000
                 DISPLAY "SQLCODE IS: " SQLCODE                         00810000
              NOT AT END                                                00820001
                 DISPLAY " "                                            00820106
                 ADD 1 TO READ-CNTR                                     00821006
           END-READ.                                                    00870000
                                                                        00880000
                                                                        00890000
       210-ERROR-CONTROL SECTION.                                       00890106
      * SECTION. CONTROLLING RECORDS FOR ERRORS.                        00890206
                                                                        00890306
      * CONTROLLING PAYMENT ID FOR ERRORS.                              00892005
                                                                        00892105
           INITIALIZE ERR-CNTR                                          00892206
           INITIALIZE OK-CNTR                                           00892306
                                                                        00892405
           EVALUATE TRUE                                                00892505
              WHEN PAYMENT-ID = SPACES                                  00892606
                 MOVE 1 TO ERR-CNTR                                     00892706
                 SET ERR-3 TO TRUE                                      00892806
                   PERFORM 299-ERROR-DISPLAY                            00892906
              WHEN PAYMENT-ID IS NOT NUMERIC                            00893005
                 MOVE 1 TO ERR-CNTR                                     00893106
                 SET ERR-1 TO TRUE                                      00893206
                   PERFORM 299-ERROR-DISPLAY                            00893306
              WHEN PAYMENT-ID IS ZERO                                   00893405
                 MOVE 1 TO ERR-CNTR                                     00893506
                 SET ERR-2 TO TRUE                                      00893606
                   PERFORM 299-ERROR-DISPLAY                            00893706
              WHEN OTHER                                                00894205
                 MOVE 1 TO OK-CNTR                                      00894306
                 ADD 1 TO INS-CNTR                                      00894406
                   PERFORM 300-MOVE-DATA                                00894506
                 CONTINUE                                               00894605
           END-EVALUATE.                                                00894706
                                                                        00894805
                                                                        00894906
       230-INVOICE-ID-CTRL.                                             00895006
      * CONTROLLING INVOICE ID FOR ERRORS.                              00895105
                                                                        00895205
           INITIALIZE ERR-CNTR                                          00895306
           INITIALIZE OK-CNTR                                           00895406
                                                                        00895506
           EVALUATE TRUE                                                00895605
              WHEN TERMIN-ID = SPACES                                   00895706
                 MOVE 2 TO ERR-CNTR                                     00895806
                 SET ERR-3 TO TRUE                                      00895906
                   PERFORM 299-ERROR-DISPLAY                            00896006
              WHEN TERMIN-ID IS NOT NUMERIC                             00896105
                 MOVE 2 TO ERR-CNTR                                     00896206
                 SET ERR-1 TO TRUE                                      00896306
                   PERFORM 299-ERROR-DISPLAY                            00896406
              WHEN TERMIN-ID IS ZERO                                    00896505
                 MOVE 2 TO ERR-CNTR                                     00896606
                 SET ERR-2 TO TRUE                                      00896706
                   PERFORM 299-ERROR-DISPLAY                            00896806
              WHEN OTHER                                                00897205
                 MOVE 2 TO OK-CNTR                                      00897306
                 ADD 1 TO INS-CNTR                                      00897406
                   PERFORM 300-MOVE-DATA                                00897506
                 CONTINUE                                               00897605
           END-EVALUATE.                                                00897706
                                                                        00898006
                                                                        00899006
       240-PAID-AMOUNT-CTRL.                                            00899106
      * CONTROLLING PAID AMOUNT FOR ERRORS.                             00899205
                                                                        00899306
           INITIALIZE ERR-CNTR                                          00899406
           INITIALIZE OK-CNTR                                           00899506
                                                                        00899606
           EVALUATE TRUE                                                00899705
              WHEN PAYMENT-ID = SPACES                                  00899806
                 MOVE 3 TO ERR-CNTR                                     00899906
                 SET ERR-3 TO TRUE                                      00900006
                   PERFORM 299-ERROR-DISPLAY                            00900106
              WHEN PAID-AMT IS NOT NUMERIC                              00900205
                 MOVE 3 TO ERR-CNTR                                     00900306
                 SET ERR-1 TO TRUE                                      00900406
                   PERFORM 299-ERROR-DISPLAY                            00900506
              WHEN PAID-AMT IS NEGATIVE                                 00901005
                 MOVE 3 TO ERR-CNTR                                     00901106
                 SET ERR-4 TO TRUE                                      00901206
                   PERFORM 299-ERROR-DISPLAY                            00901306
              WHEN OTHER                                                00901405
                 MOVE 3 TO OK-CNTR                                      00901506
                 ADD 1 TO INS-CNTR                                      00901606
                   PERFORM 300-MOVE-DATA                                00901706
                 CONTINUE                                               00901805
           END-EVALUATE.                                                00901906
                                                                        00902006
                                                                        00902105
       250-PAID-DATE-CTRL.                                              00902206
      * CONTROLLING PAID DATE FOR ERRORS.                               00902305
                                                                        00902405
           INITIALIZE ERR-CNTR                                          00902506
           INITIALIZE OK-CNTR                                           00902606
           INITIALIZE CHAR-CNTR                                         00902706
                                                                        00902906
           INSPECT PAID-DATE                                            00903005
              TALLYING CHAR-CNTR FOR ALL "/", "!", "?", "&", "@",       00903106
                                         "%", "(", ")", "*", "_",       00903206
                                         "#", "=", "}", "{", "\"        00903306
                                                                        00903406
                                                                        00903605
           IF PAID-DATE(1:10) = WS-DATE-FOR-CALC(1:10)                  00904206
           AND CHAR-CNTR > 0                                            00904306
               MOVE 4 TO ERR-CNTR                                       00904406
               SET ERR-5 TO TRUE                                        00904506
           END-IF                                                       00904606
                                                                        00904706
           IF PAID-DATE(1:10) > WS-DATE-FOR-CALC(1:10)                  00904806
           AND CHAR-CNTR = 0                                            00904906
               MOVE 4 TO ERR-CNTR                                       00905006
               SET ERR-6 TO TRUE                                        00905106
           END-IF                                                       00905206
                                                                        00905306
           IF PAID-DATE(1:10) < WS-DATE-FOR-CALC(1:10)                  00905406
           AND CHAR-CNTR = 0                                            00905506
               MOVE 4 TO ERR-CNTR                                       00905606
               SET ERR-6 TO TRUE                                        00905706
           END-IF                                                       00905806
                                                                        00905906
           IF PAID-DATE(1:10) > WS-DATE-FOR-CALC(1:10)                  00906006
           AND CHAR-CNTR > 0                                            00906106
               MOVE 4 TO ERR-CNTR                                       00906206
               SET ERR-5 TO TRUE                                        00906306
           END-IF                                                       00906406
                                                                        00906506
           IF CHAR-CNTR > 0                                             00906606
              MOVE 4 TO ERR-CNTR                                        00906706
              SET ERR-5 TO TRUE                                         00906806
           END-IF                                                       00906906
                                                                        00907006
           IF ERR-CNTR = 4                                              00907206
              PERFORM 299-ERROR-DISPLAY                                 00907306
           ELSE                                                         00907406
              MOVE 4 TO OK-CNTR                                         00907506
              ADD 1 TO INS-CNTR                                         00907606
                PERFORM 300-MOVE-DATA                                   00907706
              CONTINUE                                                  00907806
           END-IF                                                       00907906
                                                                        00908806
           INITIALIZE INS-CNTR.                                         00908906
                                                                        00909006
                                                                        00909706
       299-ERROR-DISPLAY SECTION.                                       00909806
      * DISPLAYING ERRORS FOUND IN THE INFILE.                          00909906
                                                                        00910006
           MOVE ERR-CNTR TO ERR-FLAG                                    00910106
                                                                        00910206
           DISPLAY SPACE                                                00910306
           DISPLAY ERR-MESSAGE                                          00910406
           DISPLAY "CURRENT RECORD NUMBER: " READ-CNTR                  00910506
                                                                        00910606
           EVALUATE ERR-FLAG                                            00910706
             WHEN 1                                                     00910806
                DISPLAY ERR-P-ID SPACE PAYMENT-ID SPACE ERR-REASON      00910906
             WHEN 2                                                     00911006
                DISPLAY ERR-I-ID SPACE TERMIN-ID SPACE ERR-REASON       00911106
             WHEN 3                                                     00911206
                DISPLAY ERR-AMT SPACE PAID-AMT SPACE ERR-REASON         00911306
             WHEN 4                                                     00911406
                DISPLAY ERR-DATE SPACE PAID-DATE SPACE ERR-REASON       00911506
             WHEN OTHER                                                 00911706
                DISPLAY ERR-UNKNOWN                                     00911806
           END-EVALUATE.                                                00911906
                                                                        00912006
                                                                        00912106
       300-MOVE-DATA SECTION.                                           00912206
      * MOVING VALID RECORDS TO DCLGEN HOST VARIABLES.                  00912306
                                                                        00912406
           MOVE OK-CNTR TO MOVE-FLAG                                    00912506
                                                                        00912606
           DISPLAY SPACE                                                00912706
           DISPLAY "MOVED RECORDS:"                                     00912806
           DISPLAY "CURRENT RECORD NUMBER: " READ-CNTR                  00912906
                                                                        00913006
           EVALUATE MOVE-FLAG                                           00913106
             WHEN 1                                                     00913206
                MOVE PAYMENT-ID TO PAY_PAYMENT-ID                       00913306
                DISPLAY "PAYMENT ID: " PAYMENT-ID, SPACE PAY_PAYMENT-ID 00913406
             WHEN 2                                                     00913606
                MOVE TERMIN-ID TO PAY_INVOICE-ID                        00913706
                DISPLAY "INVOICE ID: " TERMIN-ID, SPACE PAY_INVOICE-ID  00913806
             WHEN 3                                                     00914006
                MOVE PAID-AMT TO PAY_PAID-AMOUNT                        00914106
                DISPLAY "PAID AMOUNT: " PAID-AMT, SPACE PAY_PAID-AMOUNT 00914206
             WHEN 4                                                     00914406
                MOVE PAID-DATE TO PAY_PAID-DATE                         00914506
                DISPLAY "PAID DATE: " PAID-DATE, SPACE PAY_PAID-DATE    00914606
                DISPLAY SPACE                                           00914706
           END-EVALUATE.                                                00914906
                                                                        00915006
           IF INS-CNTR = 4                                              00915906
              PERFORM 310-INSERT                                        00916006
           END-IF.                                                      00916106
                                                                        00916206
                                                                        00916306
       310-INSERT SECTION.                                              00916406
      * INSERTING VALID ROWS INTO THE TABLE.                            00916506
                                                                        00916606
           DISPLAY SPACE                                                00916706
           DISPLAY "INSERTING INTO 'PAYMENT' TABLE:"                    00916806
                                                                        00916906
           EXEC SQL                                                     00917006
              INSERT INTO KALA12.PAYMENT                                00917107
                     (PAYMENT_ID,                                       00917206
                      INVOICE_ID,                                       00917306
                      PAID_AMOUNT,                                      00917406
                      PAID_DATE)                                        00917506
              VALUES (:PAY_PAYMENT-ID,                                  00917606
                      :PAY_INVOICE-ID,                                  00917706
                      :PAY_PAID-AMOUNT,                                 00917806
                      :PAY_PAID-DATE)                                   00917906
           END-EXEC                                                     00918006
                                                                        00918106
           IF SQLCODE = 0                                               00918206
              DISPLAY "INSERT WAS SUCCESSFULL. SQLCODE: "               00918306
           ELSE                                                         00918406
              DISPLAY "SQL ERROR: " SQLCODE                             00918506
           END-IF.                                                      00918606
                                                                        00918706
                                                                        00918806
       500-CLOSE-FILE SECTION.                                          00919206
      * CLOSING THE INFILE.                                             00919300
                                                                        00920000
           CLOSE PAYIN.                                                 00930000
                                                                        00940000
                                                                        00950000
