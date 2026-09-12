       IDENTIFICATION DIVISION.                                         00010001
      *---------------------------------------------------------------- 00020001
       PROGRAM-ID. LNDWISE4.                                            00030001
                                                                        00040001
       ENVIRONMENT DIVISION.                                            00050001
       INPUT-OUTPUT SECTION.                                            00060001
       FILE-CONTROL.                                                    00070001
           SELECT WS-OUTFILE-1 ASSIGN TO OUTFILE                        00080001
               ORGANIZATION IS SEQUENTIAL                               00090001
               ACCESS MODE IS SEQUENTIAL                                00100001
               FILE STATUS IS STATUS-OUTFILE1.                          00110001
                                                                        00120001
       DATA DIVISION.                                                   00130001
                                                                        00140001
       FILE SECTION.                                                    00150001
       FD WS-OUTFILE-1.                                                 00160001
       01  WS-OUTFILE-POST   PIC X(80).                                 00170001
                                                                        00180001
       WORKING-STORAGE SECTION.                                         00190001
                                                                        00200001
      *---------------------------------------------------------------- 00210001
      * Common runtime info & counters                                  00220001
      *---------------------------------------------------------------- 00230001
       01  WS-SQL-ACTION           PIC X(40).                           00240001
       01  WS-SQLCODE-DISPLAY      PIC S9(9) COMP.                      00250001
                                                                        00260001
       01  WS-CURRENT-DATE.                                             00270001
           05 WS-DATE-YYYY        PIC X(4).                             00280001
           05 WS-DATE-MM          PIC X(2).                             00290001
           05 WS-DATE-DD          PIC X(2).                             00300001
                                                                        00310001
       01  WS-DATE-GENERATED       PIC X(30).                           00320001
       01  WS-DATE-GENERATED-LINE  PIC X(50).                           00330001
       01  WS-DATE-FOR-CALC        PIC X(10).                           00340001
                                                                        00350001
       01  CURRENT-LOAN-ID         PIC S9(9) COMP.                      00360001
                                                                        00370001
      *---------------------------------------------------------------- 00380001
      * Output Record Layout                                            00390001
      *---------------------------------------------------------------- 00400001
       01  REPORT-RECORD.                                               00410001
           05 WS-CUSTOMER-ID              PIC 9(9).                     00420001
           05 FILLER                      PIC X(1).                     00430001
           05 WS-LOAN-ID                  PIC 9(9).                     00440001
           05 FILLER                      PIC X(1).                     00450001
           05 WS-LOAN-STATUS              PIC X(1).                     00460001
           05 FILLER                      PIC X(1).                     00470001
           05 WS-NEXT-PAYMENT-STATUS      PIC X(7).                     00480001
           05 FILLER                      PIC X(1).                     00490001
           05 WS-NEXT-DUE-DATE            PIC X(10).                    00500001
           05 FILLER                      PIC X(1).                     00510001
           05 WS-PREV-PAYMENT-AMT         PIC 9(15)V9(2).               00520001
           05 FILLER                      PIC X(1).                     00530001
           05 WS-PREV-INVOICE-ID          PIC 9(9).                     00540001
           05 FILLER                      PIC X(1).                     00550001
           05 WS-PREV-DATE-PAID           PIC X(10).                    00560001
           05 FILLER                      PIC X(1).                     00570001
           05 EXCESS-AMT-LOAN-COMPLETION  PIC 9(15)V9(2).               00580001
           05 FILLER                      PIC X(1).                     00590001
           05 WS-TOTAL-INTEREST-EARNED    PIC 9(15)V9(2).               00600001
                                                                        00610001
       01 STATUS-OUTFILE1          PIC X(2).                            00620001
       01 WS-RETURN-CODE           PIC S9(4) COMP.                      00630001
                                                                        00640001
      *---------------------------------------------------------------- 00650001
      * Variables for payment and leftover calculations                 00660001
      *---------------------------------------------------------------- 00670001
       01  LEFTOVER-PAYMENT        PIC S9(15)V9(2) COMP-3.              00680001
       01  EXCESS-PAYMENT          PIC S9(15)V9(2) COMP-3.              00690001
       01  EXCESS-LOAN-PAYMENT     PIC S9(15)V9(2) COMP-3 VALUE 0.      00700001
       01  TOT-EXCESS-PAYMENT      PIC S9(15)V9(2) COMP-3 VALUE 0.      00710001
       01  WS-PERIOD-DEC           PIC S9(11)V9(2) COMP-3 VALUE 0.      00720001
                                                                        00730001
       01  CURRENT-INVOICE-NUMBER  PIC 9(9).                            00740001
       01  NUMBER-OF-INVOICES-PAID PIC S9(9) COMP.                      00750001
       01  WS-NO-INVOICES-PAID     PIC S9(9).                           00760001
       01  ACCUMULATED-TOT-PAYMENTS PIC S9(15)V9(2) COMP-3 VALUE 0.     00770001
       01  ADJUSTED-MONTHLY-PAYMENT PIC S9(15)V9(2) COMP-3 VALUE 0.     00780001
                                                                        00790001
      *---------------------------------------------------------------- 00800001
      * Variables for interest/loan math                                00810001
      *---------------------------------------------------------------- 00820001
       01  MONTHLY-INTEREST-RATE   PIC S9(2)V9(2) COMP-3.               00830001
       01  REMAINING-PRINCIPAL     PIC S9(15)V9(2) COMP-3.              00840001
       01  INTEREST-PAYMENT        PIC S9(15)V9(2) COMP-3.              00850001
       01  PRINCIPAL-PAYMENT       PIC S9(15)V9(2) COMP-3.              00860001
       01  TOTAL-INTEREST-PAID     PIC S9(15)V9(2) COMP-3 VALUE 0.      00870001
       01  TOTAL_PRINCIPAL_PAID    PIC S9(15)V9(2) COMP-3 VALUE 0.      00880001
                                                                        00890001
       01  TOTAL_PAYMENT_PAID      PIC S9(15)V9(2) COMP-3.              00900001
       01  TOTAL_FULL_PAYMENT      PIC S9(15)V9(2) COMP-3 VALUE 0.      00910001
       01  TOTAL_PAYMENT_REMAINING PIC S9(15)V9(2) COMP-3.              00920001
       01  TOTAL_POTENTIAL_AMOUNT  PIC S9(15)V9(2) COMP-3 VALUE 0.      00930001
       01  ACTUAL-MONEY-TO-BANK    PIC S9(15)V9(2) COMP-3.              00940001
       01  TOTAL-EXCESS-AMOUNT     PIC S9(15)V9(2) COMP-3.              00950001
                                                                        00960001
      *---------------------------------------------------------------- 00970001
      * For display/debugging                                           00980001
      *---------------------------------------------------------------- 00990001
       01  WS-DISPLAY-NUMBER       PIC S9(9) COMP.                      01000001
       01  WS-TEST-DISPLAY         PIC X(30).                           01010001
       01  WS-NULL-PAYMENT-DATE    PIC S9(4) COMP VALUE 0.              01020001
       01  WS-COUNTER              PIC 9(4).                            01030001
                                                                        01040001
           EXEC SQL                                                     01050001
             INCLUDE SQLCA                                              01060001
           END-EXEC.                                                    01070001
                                                                        01080001
           EXEC SQL                                                     01090001
             INCLUDE PLAN                                               01100001
           END-EXEC.                                                    01110001
                                                                        01120001
           EXEC SQL                                                     01130001
             INCLUDE PAYMENT                                            01140001
           END-EXEC.                                                    01150001
                                                                        01160001
           EXEC SQL                                                     01170001
             INCLUDE LOAN                                               01180001
           END-EXEC.                                                    01190001
                                                                        01200001
      *---------------------------------------------------------------- 01210001
      * Cursor that selects plan lines to process                       01220001
      *---------------------------------------------------------------- 01230001
           EXEC SQL                                                     01240001
             DECLARE C-UPDATE-PLAN CURSOR WITH HOLD FOR                 01250001
               SELECT                                                   01260001
                PAYPLAN.INVOICE_ID,                                     01270001
                PAYPLAN.LOAN_ID,                                        01280001
                PAYPLAN.DUE_DATE,                                       01290001
                PAYPLAN.PAYMENT_AMOUNT,                                 01300001
                PAYPLAN.PLAN_STATUS,                                    01310001
                PAYPLAN.REMAINING_AMOUNT,                               01320001
                PAYPLAN.REMAINING_LOAN,                                 01330001
                PAYPLAN.INTEREST_RATE,                                  01340001
                COALESCE(PAYMENT.INVOICE_ID,'0'),                       01350001
                COALESCE(PAYMENT.PAID_AMOUNT, '0'),                     01360001
                PAYMENT.PAID_DATE,                                      01370001
                LOAN.CUSTOMER_ID,                                       01380001
                LOAN.LOAN_ID,                                           01390001
                LOAN.LOAN_AMOUNT,                                       01400001
                LOAN.LOAN_STATUS,                                       01410001
                LOAN.PAYMENT_PERIOD,                                    01420001
                LOAN.CREATION_DATE                                      01430001
              FROM   PAYPLAN                                            01440001
              LEFT JOIN PAYMENT                                         01450001
                     ON PAYPLAN.INVOICE_ID = PAYMENT.INVOICE_ID         01460001
              JOIN LOAN                                                 01470001
                     ON PAYPLAN.LOAN_ID = LOAN.LOAN_ID                  01480001
              WHERE PAYPLAN.PLAN_STATUS IN ('DUE','PARTIAL','OVERDUE')  01490001
              FOR UPDATE OF                                             01500001
                REMAINING_AMOUNT,                                       01510001
                PLAN_STATUS,                                            01520001
                REMAINING_LOAN,                                         01530001
                LOAN_STATUS                                             01540001
           END-EXEC.                                                    01550001
                                                                        01560001
       PROCEDURE DIVISION.                                              01570001
                                                                        01580001
      *---------------------------------------------------------------- 01590001
      * Main Program Flow                                               01600001
      *---------------------------------------------------------------- 01610001
           PERFORM 500-INITIALIZE-PART2                                 01620001
                                                                        01630001
           PERFORM 600-FETCH-EXPECTED-PAYMENTS                          01640001
           PERFORM UNTIL SQLCODE NOT = 0                                01650001
               PERFORM 700-PAYMENT-CHECK                                01660001
               PERFORM 900-LOAN-TABLE-CHECK                             01670001
               PERFORM 1000-PROCESS-FOR-WRITING                         01680001
               PERFORM 600-FETCH-EXPECTED-PAYMENTS                      01690001
           END-PERFORM                                                  01700001
                                                                        01710001
           PERFORM 1200-CLOSE-PART2                                     01720001
           STOP RUN.                                                    01730001
                                                                        01740001
      *---------------------------------------------------------------- 01750001
      * 500-INITIALIZE-PART2                                            01760001
      *---------------------------------------------------------------- 01770001
       500-INITIALIZE-PART2.                                            01780001
           EXEC SQL                                                     01790001
             OPEN C-UPDATE-PLAN                                         01800001
           END-EXEC                                                     01810001
           MOVE "OPEN C-UPDATE-PLAN" TO WS-SQL-ACTION                   01820001
           PERFORM CHECK-SQLCODE                                        01830001
                                                                        01840001
           OPEN OUTPUT WS-OUTFILE-1                                     01850001
                                                                        01860001
           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD                    01870001
                                                                        01880001
           STRING WS-DATE-DD "-" WS-DATE-MM "-" WS-DATE-YYYY            01890001
             DELIMITED BY SIZE                                          01900001
             INTO WS-DATE-GENERATED                                     01910001
                                                                        01920001
           STRING "GENERATED ON: " DELIMITED BY SIZE                    01930001
                  WS-DATE-GENERATED DELIMITED BY SIZE                   01940001
             INTO WS-DATE-GENERATED-LINE                                01950001
                                                                        01960001
           WRITE WS-OUTFILE-POST FROM WS-CURRENT-DATE                   01970001
           .                                                            01980001
                                                                        01990001
      *---------------------------------------------------------------- 02000001
      * 600-FETCH-EXPECTED-PAYMENTS                                     02010001
      *---------------------------------------------------------------- 02020001
       600-FETCH-EXPECTED-PAYMENTS.                                     02030001
           EXEC SQL                                                     02040001
             FETCH C-UPDATE-PLAN                                        02050001
               INTO :PLAN_INVOICE-ID,                                   02060001
                    :PLAN_LOAN-ID,                                      02070001
                    :PLAN_DUE-DATE,                                     02080001
                    :PLAN_PAYMENT-AMOUNT,                               02090001
                    :PLAN_PLAN-STATUS,                                  02100001
                    :PLAN_REMAINING-AMOUNT,                             02110001
                    :PLAN_REMAINING-LOAN,                               02120001
                    :PLAN_INTEREST-RATE,                                02130001
                                                                        02140001
                    :PAY_INVOICE-ID,                                    02150001
                    :PAY_PAID-AMOUNT,                                   02160001
                    :PAY_PAID-DATE:WS-NULL-PAYMENT-DATE,                02170001
                                                                        02180001
                    :LOAN_CUSTOMER-ID,                                  02190001
                    :LOAN_LOAN-ID,                                      02200001
                    :LOAN_LOAN-AMOUNT,                                  02210001
                    :LOAN_LOAN-STATUS,                                  02220001
                    :LOAN_PAYMENT-PERIOD,                               02230001
                    :LOAN_CREATION-DATE                                 02240001
           END-EXEC                                                     02250001
                                                                        02260001
           MOVE "FETCH C-UPDATE-PLAN" TO WS-SQL-ACTION                  02270001
           PERFORM CHECK-SQLCODE                                        02280001
                                                                        02290001
           DISPLAY PLAN_INVOICE-ID                                      02300001
           DISPLAY PLAN_LOAN-ID                                         02310001
           DISPLAY PLAN_DUE-DATE                                        02320001
           DISPLAY PLAN_PAYMENT-AMOUNT                                  02330001
           DISPLAY PLAN_PLAN-STATUS                                     02340001
           DISPLAY PLAN_REMAINING-AMOUNT                                02350001
           DISPLAY PLAN_REMAINING-LOAN                                  02360001
           DISPLAY PLAN_INTEREST-RATE                                   02370001
                                                                        02380001
           DISPLAY PAY_PAID-AMOUNT                                      02390001
           DISPLAY PAY_PAID-DATE                                        02400001
                                                                        02410001
           DISPLAY LOAN_CUSTOMER-ID                                     02420001
           DISPLAY LOAN_LOAN-ID                                         02430001
           DISPLAY LOAN_LOAN-STATUS                                     02440001
           DISPLAY LOAN_PAYMENT-PERIOD                                  02450001
           DISPLAY LOAN_CREATION-DATE                                   02460001
           .                                                            02470001
                                                                        02480001
      *---------------------------------------------------------------- 02490001
      * 700-PAYMENT-CHECK                                               02500001
      *---------------------------------------------------------------- 02510001
       700-PAYMENT-CHECK.                                               02520001
           EVALUATE TRUE                                                02530001
             WHEN PAY_PAID-AMOUNT > 0                                   02540001
               PERFORM 720-PAYMENT-FOUND-CALC                           02550001
             WHEN PAY_PAID-AMOUNT = 0                                   02560001
               PERFORM 740-PAYMENT-NOT-FOUND                            02570001
             WHEN OTHER                                                 02580001
               MOVE "PAYMENT CHECK" TO WS-SQL-ACTION                    02590001
               PERFORM CHECK-SQLCODE                                    02600001
           END-EVALUATE                                                 02610001
           .                                                            02620001
                                                                        02630001
      *---------------------------------------------------------------- 02640001
      * 720-PAYMENT-FOUND-CALC                                          02650001
      *---------------------------------------------------------------- 02660001
       720-PAYMENT-FOUND-CALC.                                          02670001
           COMPUTE LEFTOVER-PAYMENT =                                   02680001
                     PLAN_REMAINING-AMOUNT - PAY_PAID-AMOUNT            02690001
                                                                        02700001
           EVALUATE TRUE                                                02710001
             WHEN LEFTOVER-PAYMENT > 0                                  02720001
               MOVE 'PARTIAL' TO PLAN_PLAN-STATUS                       02730001
               PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS                   02740001
                                                                        02750001
             WHEN LEFTOVER-PAYMENT = 0                                  02760001
               MOVE 'PAID' TO PLAN_PLAN-STATUS                          02770001
               PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS                   02780001
                                                                        02790001
             WHEN LEFTOVER-PAYMENT < 0                                  02800001
               MOVE 'PAID' TO PLAN_PLAN-STATUS                          02810001
               MOVE 0 TO PLAN_REMAINING-AMOUNT                          02820001
               PERFORM 760-OVERPAYMENT-SUBROUTINE                       02830001
           END-EVALUATE                                                 02840001
           .                                                            02850001
                                                                        02860001
      *---------------------------------------------------------------- 02870001
      * 760-OVERPAYMENT-SUBROUTINE                                      02880001
      *---------------------------------------------------------------- 02890001
       760-OVERPAYMENT-SUBROUTINE.                                      02900001
           PERFORM OPEN-OVERPAYMENT-CURSOR                              02910001
                                                                        02920001
           PERFORM UNTIL SQLCODE = 100                                  02930001
               PERFORM 01-OVERPAYMENT-UPDATE                            02940001
               PERFORM 02-OVERPAYMENT-PROCESSING                        02950001
           END-PERFORM                                                  02960001
                                                                        02970001
           PERFORM CLOSE-OVERPAYMENT-CURSOR                             02980001
           EXIT                                                         02990001
           .                                                            03000001
                                                                        03010001
      *---------------------------------------------------------------- 03020001
      * 01-OVERPAYMENT-UPDATE                                           03030001
      *---------------------------------------------------------------- 03040001
       01-OVERPAYMENT-UPDATE.                                           03050001
           DISPLAY 'CURRENT LOAN ID ' PLAN_LOAN-ID                      03060001
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID                        03070001
           DISPLAY 'STATUS WILL UPDATE TO ' PLAN_PLAN-STATUS            03080001
                                                                        03090001
           EXEC SQL                                                     03100001
             UPDATE PAYPLAN                                             03110001
                SET REMAINING_AMOUNT = :PLAN_REMAINING-AMOUNT,          03120001
                    PLAN_STATUS      = :PLAN_PLAN-STATUS                03130001
              WHERE INVOICE_ID = :PLAN_INVOICE-ID                       03140001
           END-EXEC                                                     03150001
           MOVE "UPDATE FOR OVERPAYMENT" TO WS-SQL-ACTION               03160001
           PERFORM CHECK-SQLCODE                                        03170001
                                                                        03180001
           COMPUTE EXCESS-PAYMENT = LEFTOVER-PAYMENT * (-1)             03190001
           .                                                            03200001
                                                                        03210001
      *---------------------------------------------------------------- 03220001
      * OPEN-OVERPAYMENT-CURSOR                                         03230001
      *---------------------------------------------------------------- 03240001
       OPEN-OVERPAYMENT-CURSOR.                                         03250001
           DISPLAY 'CURRENT LOAN ID ' PLAN_LOAN-ID                      03260001
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID                        03270001
                                                                        03280001
           EXEC SQL                                                     03290001
             DECLARE C-OVERPAY CURSOR WITH HOLD FOR                     03300001
               SELECT INVOICE_ID,                                       03310001
                      PAYMENT_AMOUNT,                                   03320001
                      PLAN_STATUS,                                      03330001
                      REMAINING_AMOUNT,                                 03340001
                      DUE_DATE                                          03350001
                 FROM PAYPLAN                                           03360001
                WHERE LOAN_ID    = :PLAN_LOAN-ID                        03370001
                  AND INVOICE_ID > :PLAN_INVOICE-ID                     03380001
                  AND PLAN_STATUS IN ('DUE','PARTIAL','OVERDUE')        03390001
                ORDER BY DUE_DATE                                       03400001
           END-EXEC.                                                    03410001
                                                                        03420001
           EXEC SQL                                                     03430001
             OPEN C-OVERPAY                                             03440001
           END-EXEC                                                     03450001
           MOVE "OPEN C-OVERPAY" TO WS-SQL-ACTION                       03460001
           PERFORM CHECK-SQLCODE                                        03470001
                                                                        03480001
           DISPLAY 'CURRENT LOAN ID ' CURRENT-LOAN-ID                   03490001
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID                        03500001
           .                                                            03510001
                                                                        03520001
      *---------------------------------------------------------------- 03530001
      * 02-OVERPAYMENT-PROCESSING                                       03540001
      *---------------------------------------------------------------- 03550001
       02-OVERPAYMENT-PROCESSING.                                       03560001
           EXEC SQL                                                     03570001
             FETCH C-OVERPAY                                            03580001
               INTO :PLAN_INVOICE-ID,                                   03590001
                    :PLAN_PAYMENT-AMOUNT,                               03600001
                    :PLAN_PLAN-STATUS,                                  03610001
                    :PLAN_REMAINING-AMOUNT,                             03620001
                    :PLAN_DUE-DATE                                      03630001
           END-EXEC                                                     03640001
           MOVE "FETCH C-OVERPAY" TO WS-SQL-ACTION                      03650001
           PERFORM CHECK-SQLCODE                                        03660001
                                                                        03670001
           EVALUATE TRUE                                                03680001
             WHEN SQLCODE = 100                                         03690001
               MOVE EXCESS-PAYMENT TO EXCESS-LOAN-PAYMENT               03700001
               EXIT                                                     03710001
             WHEN OTHER                                                 03720001
               PERFORM 02A-OVERPAYMENT-CALCULATIONS                     03730001
           END-EVALUATE                                                 03740001
           .                                                            03750001
                                                                        03760001
      *---------------------------------------------------------------- 03770001
      * 02A-OVERPAYMENT-CALCULATIONS                                    03780001
      *---------------------------------------------------------------- 03790001
       02A-OVERPAYMENT-CALCULATIONS.                                    03800001
           COMPUTE LEFTOVER-PAYMENT =                                   03810001
                     PLAN_REMAINING-AMOUNT - EXCESS-PAYMENT             03820001
                                                                        03830001
           MOVE LEFTOVER-PAYMENT TO PLAN_REMAINING-AMOUNT               03840001
                                                                        03850001
           DISPLAY 'LEFTOVER-PAYMENT AT ' PLAN_INVOICE-ID ' IS '        03860001
                   LEFTOVER-PAYMENT ' READ AT PARA 03'                  03870001
                                                                        03880001
           EVALUATE TRUE                                                03890001
             WHEN LEFTOVER-PAYMENT = 0                                  03900001
               MOVE 'PAID'    TO PLAN_PLAN-STATUS                       03910001
             WHEN LEFTOVER-PAYMENT > 0                                  03920001
               MOVE 'PARTIAL' TO PLAN_PLAN-STATUS                       03930001
             WHEN LEFTOVER-PAYMENT < 0                                  03940001
               MOVE 'PAID'    TO PLAN_PLAN-STATUS                       03950001
               MOVE 0         TO PLAN_REMAINING-AMOUNT                  03960001
           END-EVALUATE                                                 03970001
           .                                                            03980001
                                                                        03990001
      *---------------------------------------------------------------- 04000001
      * CLOSE-OVERPAYMENT-CURSOR                                        04010001
      *---------------------------------------------------------------- 04020001
       CLOSE-OVERPAYMENT-CURSOR.                                        04030001
           EXEC SQL                                                     04040001
             CLOSE C-OVERPAY                                            04050001
           END-EXEC                                                     04060001
           MOVE "CLOSE C-OVERPAY" TO WS-SQL-ACTION                      04070001
           PERFORM CHECK-SQLCODE                                        04080001
           .                                                            04090001
                                                                        04100001
      *---------------------------------------------------------------- 04110001
      * 740-PAYMENT-NOT-FOUND                                           04120001
      *---------------------------------------------------------------- 04130001
       740-PAYMENT-NOT-FOUND.                                           04140001
                                                                        04150001
           STRING WS-DATE-YYYY "-" WS-DATE-MM "-" WS-DATE-DD            04160001
             DELIMITED BY SIZE                                          04170001
             INTO WS-DATE-FOR-CALC                                      04180001
                                                                        04190001
           IF PLAN_DUE-DATE(1:10) < WS-DATE-FOR-CALC(1:10)              04200001
                                                                        04210001
              EVALUATE TRUE                                             04220001
                WHEN PLAN_PLAN-STATUS NOT = 'PARTIAL'                   04230001
                  MOVE PLAN_PAYMENT-AMOUNT TO LEFTOVER-PAYMENT          04240001
                  PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS                04250001
                WHEN PLAN_PLAN-STATUS = 'PARTIAL'                       04260001
                  EXIT                                                  04270001
              END-EVALUATE                                              04280001
           END-IF                                                       04290001
                                                                        04300001
           INITIALIZE LEFTOVER-PAYMENT                                  04310001
           .                                                            04320001
                                                                        04330001
      *---------------------------------------------------------------- 04340001
      * 800-UPDATE-PAYMENT-PLAN-STATUS                                  04350001
      *---------------------------------------------------------------- 04360001
       800-UPDATE-PAYMENT-PLAN-STATUS.                                  04370001
           EXEC SQL                                                     04380001
             UPDATE PAYPLAN                                             04390001
                SET REMAINING_AMOUNT = :LEFTOVER-PAYMENT,               04400001
                    PLAN_STATUS      = :PLAN_PLAN-STATUS                04410001
              WHERE INVOICE_ID = :PLAN_INVOICE-ID                       04420001
           END-EXEC                                                     04430001
                                                                        04440001
           MOVE "UPDATE PAYMENT PLAN TABLE" TO WS-SQL-ACTION            04450001
           PERFORM CHECK-SQLCODE                                        04460001
           .                                                            04470001
                                                                        04480001
      *---------------------------------------------------------------- 04490001
      * 900-LOAN-TABLE-CHECK                                            04500001
      * CALCULATES REMAINING LOAN BALANCE AND HAS LOGIC TO CHECK        04510001
      * IF LOAN PLAN SHOULD BE DELETED OR JUST UPDATED.                 04520001
      * FIRST IT FETCHES THE NUMBER OF PAYMENTS MADE BY A CUSTOMER AND  04530001
      * SUMS THE AMOUNT SO WE SEE WHAT THEIR TOTAL PAYMENT IS.          04540001
      * THEN WE USE PERFORM VARYING TO LOOP THROUGH ALL PAYMENTS TO     04550001
      * CALCULATE TOTAL PRINCIPAL PAYMENT TOTAL INTEREST AND            04560001
      * FINALLY TOTAL REMAINING BALANCE.                                04570001
      *---------------------------------------------------------------- 04580001
       900-LOAN-TABLE-CHECK.                                            04590001
           EXEC SQL                                                     04600001
             SELECT COUNT(*),                                           04610001
                    SUM(P.PAID_AMOUNT)                                  04620001
               INTO :NUMBER-OF-INVOICES-PAID,                           04630001
                    :ACCUMULATED-TOT-PAYMENTS                           04640001
               FROM PAYMENT P                                           04650001
               JOIN PAYPLAN PPS                                         04660001
                  ON P.INVOICE_ID = PPS.INVOICE_ID                      04670001
              WHERE PPS.LOAN_ID = :PLAN_LOAN-ID                         04680001
           END-EXEC                                                     04690001
                                                                        04700001
           MOVE "FINDING NUMBER OF INSTALLMENTS PAID                    04710001
      -         "AND SUM OF PAYMENTS"                                   04720001
                 TO WS-SQL-ACTION                                       04730001
           PERFORM CHECK-SQLCODE                                        04740001
                                                                        04750001
           MOVE NUMBER-OF-INVOICES-PAID TO WS-NO-INVOICES-PAID          04760001
                                                                        04770001
           COMPUTE ADJUSTED-MONTHLY-PAYMENT =                           04780001
                   ACCUMULATED-TOT-PAYMENTS / WS-NO-INVOICES-PAID       04790001
                                                                        04800001
           COMPUTE MONTHLY-INTEREST-RATE =                              04810001
                   (PLAN_INTEREST-RATE / 12)                            04820001
                                                                        04830001
           MOVE LOAN_LOAN-AMOUNT TO REMAINING-PRINCIPAL                 04840001
                                                                        04850001
           PERFORM VARYING WS-COUNTER FROM 1 BY 1                       04860001
                   UNTIL WS-COUNTER > WS-NO-INVOICES-PAID               04870001
                                                                        04880001
               COMPUTE INTEREST-PAYMENT =                               04890001
                        (REMAINING-PRINCIPAL * MONTHLY-INTEREST-RATE)   04900001
                        / 100                                           04910001
                                                                        04920001
               COMPUTE PRINCIPAL-PAYMENT =                              04930001
                        ADJUSTED-MONTHLY-PAYMENT - INTEREST-PAYMENT     04940001
                                                                        04950001
               COMPUTE REMAINING-PRINCIPAL =                            04960001
                       REMAINING-PRINCIPAL - PRINCIPAL-PAYMENT          04970001
                                                                        04980001
               ADD INTEREST-PAYMENT   TO TOTAL-INTEREST-PAID            04990001
               ADD PRINCIPAL-PAYMENT  TO TOTAL_PRINCIPAL_PAID           05000001
                                                                        05010001
           END-PERFORM                                                  05020001
                                                                        05030001
           COMPUTE TOTAL_POTENTIAL_AMOUNT =                             05040001
                  (WS-PERIOD-DEC * PLAN_PAYMENT-AMOUNT)                 05050001
                                                                        05060001
           COMPUTE ACTUAL-MONEY-TO-BANK =                               05070001
                   TOTAL-INTEREST-PAID + LOAN_LOAN-AMOUNT               05080001
                                                                        05090001
           COMPUTE TOTAL-EXCESS-AMOUNT =                                05100001
                   TOTAL_POTENTIAL_AMOUNT - ACTUAL-MONEY-TO-BANK        05110001
                                                                        05120001
           MOVE REMAINING-PRINCIPAL TO TOTAL_PAYMENT_REMAINING          05130001
                                                                        05140001
           DISPLAY 'CURRENT-INVOICE-NUMBER '    CURRENT-INVOICE-NUMBER  05150001
           DISPLAY 'WS-NO-INVOICES-PAID  '      WS-NO-INVOICES-PAID     05160001
           DISPLAY 'INTEREST-PAYMENT '          INTEREST-PAYMENT        05170001
           DISPLAY 'TOTAL-INTEREST-PAID '       TOTAL-INTEREST-PAID     05180001
           DISPLAY 'PRINCIPAL-PAYMENT '         PRINCIPAL-PAYMENT       05190001
           DISPLAY 'REMAINING-PRINCIPAL '       REMAINING-PRINCIPAL     05200001
           DISPLAY 'TOTAL_PAYMENT_PAID '        TOTAL_PAYMENT_PAID      05210001
           DISPLAY 'TOTAL_FULL_PAYMENT '        TOTAL_FULL_PAYMENT      05220001
           DISPLAY 'TOTAL_PAYMENT_REMAINING '   TOTAL_PAYMENT_REMAINING 05230001
                                                                        05240001
           EVALUATE TRUE                                                05250001
             WHEN REMAINING-PRINCIPAL > 0                               05260001
               PERFORM 910-LOAN-AMOUNT-UPDATE                           05270001
             WHEN REMAINING-PRINCIPAL = 0                               05280001
               PERFORM 920-LOAN-DELETE                                  05290001
             WHEN REMAINING-PRINCIPAL < 0                               05300001
               COMPUTE TOT-EXCESS-PAYMENT = REMAINING-PRINCIPAL * (-1)  05310001
               PERFORM 920-LOAN-DELETE                                  05320001
           END-EVALUATE                                                 05330001
           .                                                            05340001
                                                                        05350001
      *---------------------------------------------------------------- 05360001
      * 910-LOAN-AMOUNT-UPDATE                                          05370001
      *---------------------------------------------------------------- 05380001
       910-LOAN-AMOUNT-UPDATE.                                          05390001
           EXEC SQL                                                     05400001
             UPDATE PAYPLAN                                             05410001
                SET REMAINING_LOAN = :REMAINING-PRINCIPAL               05420001
              WHERE INVOICE_ID = :PLAN_INVOICE-ID                       05430001
           END-EXEC                                                     05440001
           MOVE "UPDATE TOTAL LOAN-AMOUNT" TO WS-SQL-ACTION             05450001
           PERFORM CHECK-SQLCODE                                        05460001
           .                                                            05470001
                                                                        05480001
      *---------------------------------------------------------------- 05490001
      * 920-LOAN-DELETE                                                 05500001
      *---------------------------------------------------------------- 05510001
       920-LOAN-DELETE.                                                 05520001
           MOVE 'C' TO LOAN_LOAN-STATUS                                 05530001
                                                                        05540001
           EXEC SQL                                                     05550001
             UPDATE LOAN                                                05560001
                SET LOAN_STATUS = :LOAN_LOAN-STATUS                     05570001
              WHERE LOAN_ID    = :PLAN_LOAN-ID                          05580001
           END-EXEC                                                     05590001
           MOVE "UPDATE LOAN STATUS" TO WS-SQL-ACTION                   05600001
           PERFORM CHECK-SQLCODE                                        05610001
                                                                        05620001
           MOVE EXCESS-LOAN-PAYMENT TO EXCESS-AMT-LOAN-COMPLETION       05630001
                                                                        05640001
           EXEC SQL                                                     05650001
             DELETE FROM PAYPLAN                                        05660001
              WHERE LOAN_ID = :PLAN_LOAN-ID                             05670001
           END-EXEC                                                     05680001
           MOVE "DELETE CURRENT PLAN FOR LOAN" TO WS-SQL-ACTION         05690001
           PERFORM CHECK-SQLCODE                                        05700001
           .                                                            05710001
                                                                        05720001
      *---------------------------------------------------------------- 05730001
      * 1000-PROCESS-FOR-WRITING                                        05740001
      *---------------------------------------------------------------- 05750001
       1000-PROCESS-FOR-WRITING.                                        05760001
           MOVE LOAN_CUSTOMER-ID   TO WS-CUSTOMER-ID                    05770001
           MOVE LOAN_LOAN-ID       TO WS-LOAN-ID                        05780001
           MOVE LOAN_LOAN-STATUS   TO WS-LOAN-STATUS                    05790001
           MOVE PLAN_PLAN-STATUS   TO WS-NEXT-PAYMENT-STATUS            05800001
           MOVE PLAN_DUE-DATE      TO WS-NEXT-DUE-DATE                  05810001
           MOVE PAY_PAID-AMOUNT    TO WS-PREV-PAYMENT-AMT               05820001
           MOVE PAY_INVOICE-ID     TO WS-PREV-INVOICE-ID                05830001
           MOVE PAY_PAID-DATE      TO WS-PREV-DATE-PAID                 05840001
           MOVE TOT-EXCESS-PAYMENT TO EXCESS-AMT-LOAN-COMPLETION        05850001
                                                                        05860001
           WRITE WS-OUTFILE-POST FROM REPORT-RECORD                     05870001
           .                                                            05880001
                                                                        05890001
      *---------------------------------------------------------------- 05900001
      * 1200-CLOSE-PART2                                                05910001
      *---------------------------------------------------------------- 05920001
       1200-CLOSE-PART2.                                                05930001
           EXEC SQL                                                     05940001
             CLOSE C-UPDATE-PLAN                                        05950001
           END-EXEC                                                     05960001
           MOVE "CLOSE C-PLAN CURSOR" TO WS-SQL-ACTION                  05970001
           PERFORM CHECK-SQLCODE                                        05980001
                                                                        05990001
           CLOSE WS-OUTFILE-1                                           06000001
           .                                                            06010001
                                                                        06020001
      *---------------------------------------------------------------- 06030001
      * CHECK-SQLCODE                                                   06040001
      *    Common routine to handle SQL statuses                        06050001
      *---------------------------------------------------------------- 06060001
       CHECK-SQLCODE.                                                   06070001
           MOVE SQLCODE TO WS-SQLCODE-DISPLAY                           06080001
           EVALUATE SQLCODE                                             06090001
             WHEN 0                                                     06100001
               DISPLAY "SUCCESSFUL SQL ACTION: " WS-SQL-ACTION          06110001
             WHEN 100                                                   06120001
               DISPLAY "NO ROWS FOR SQL ACTION: " WS-SQL-ACTION         06130001
             WHEN OTHER                                                 06140001
               DISPLAY "ABEND DUE TO SQL ERROR DURING: " WS-SQL-ACTION  06150001
               DISPLAY "SQLCODE=" WS-SQLCODE-DISPLAY                    06160001
               PERFORM ABEND-PARA                                       06170001
           END-EVALUATE                                                 06180001
           EXIT.                                                        06190001
                                                                        06200001
      *---------------------------------------------------------------- 06210001
      * ABEND-PARA                                                      06220001
      *---------------------------------------------------------------- 06230001
       ABEND-PARA.                                                      06240001
           DISPLAY "ABEND ACTIVATED"                                    06250001
           MOVE 1111 TO WS-RETURN-CODE                                  06260001
           CALL 'CEE3ABD' USING WS-RETURN-CODE                          06270001
           GOBACK                                                       06280001
           .                                                            06290001
                                                                        06300001
      *---------------------------------------------------------------- 06310001
      * TEST-DISPLAY-PARA                                               06320001
      *---------------------------------------------------------------- 06330001
       TEST-DISPLAY-PARA.                                               06340001
           DISPLAY WS-TEST-DISPLAY ' ' WS-DISPLAY-NUMBER                06350001
           EXIT.                                                        06360001
                                                                        06370001
      *---------------------------------------------------------------- 06380001
      * DESIGN-REPORTS                                                  06390001
      *---------------------------------------------------------------- 06400001
       DESIGN-REPORTS.                                                  06410001
           EXIT.                                                        06420001
