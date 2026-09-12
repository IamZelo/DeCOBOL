       IDENTIFICATION DIVISION.                                         00010004
       PROGRAM-ID. WONA.                                                00020030
                                                                        00021018
       ENVIRONMENT DIVISION.                                            00030004
       DATA DIVISION.                                                   00110004
       WORKING-STORAGE SECTION.                                         00180004
                                                                        00200004
      ******************************************************            00210030
      *     HOST VARIABLE DECLARATION FOR TABLE PAYPLAN    *            00211030
      ******************************************************            00212030
                                                                        00213030
      *01 PLAN_LOAN-ID                PIC S9(9) USAGE COMP.             00214030
      *01 PLAN_DUE-DATE               PIC X(10).                        00215030
      *01 PLAN_PAYMENT-AMOUNT         PIC S9(15)V9(2) USAGE COMP-3.     00216030
      *01 PLAN_REMAINING-AMOUNT       PIC S9(15)V9(2) USAGE COMP-3.     00217030
      *01 PLAN_REMAINING-LOAN         PIC S9(15)V9(2) USAGE COMP-3.     00218030
      *01 PLAN_INTEREST-RATE          PIC S9(2)V9(2) USAGE COMP-3.      00219030
                                                                        00220004
           EXEC SQL                                                     00230004
              INCLUDE SQLCA                                             00240004
           END-EXEC.                                                    00250004
                                                                        00260004
           EXEC SQL                                                     00270004
              INCLUDE CUSTOMER                                          00280004
           END-EXEC.                                                    00290004
                                                                        00300004
           EXEC SQL                                                     00310004
              INCLUDE LOAN                                              00320014
           END-EXEC.                                                    00330004
                                                                        00340004
           EXEC SQL                                                     00350004
              INCLUDE PAYPLAN                                           00360018
           END-EXEC.                                                    00370004
                                                                        00380004
           EXEC SQL                                                     00390004
              INCLUDE LOANTYPE                                          00400014
           END-EXEC.                                                    00410004
                                                                        00420004
                                                                        00460004
      *****************************************************             00461030
      *              DECLARE CURSOR FOR LOAN              *             00462030
      *****************************************************             00463030
           EXEC SQL                                                     00470004
              DECLARE C1 CURSOR FOR                                     00480023
               SELECT LOAN_ID                                           00480123
                    , CUSTOMER_ID                                       00500023
                    , TYPE_ID                                           00510023
                    , LOAN_AMOUNT                                       00520023
                    , LOAN_STATUS                                       00530023
                    , INTEREST_RATE                                     00540023
                    , INTEREST_TYPE                                     00550023
                    , CREATION_DATE                                     00560023
                    , DOWN_PAYMENT                                      00570023
                    , PAYMENT_PERIOD                                    00580023
                 FROM LOAN                                              00590031
           END-EXEC.                                                    00600004
                                                                        00616229
                                                                        00619930
       01 WS-PAYMENT-PERIOD           PIC 9(9).                         00620030
                                                                        00690106
       01 WS-MULTIPLIER               PIC 9V9(2).                       00701007
                                                                        00701130
       01 WS-INTEREST-DECIMAL         PIC 9V9(4).                       00701230
                                                                        00701330
       01 WS-PRINCIPAL                PIC 9(15)V9(2).                   00701430
                                                                        00701521
       01 WS-COUNT                    PIC 99.                           00701628
                                                                        00701730
       01 WS-TOTAL-LOAN               PIC 9(15)V9(2).                   00701830
                                                                        00701930
       01 WS-NUM-DATE.                                                  00702030
         05 WS-NUM-YEAR               PIC 9(4).                         00702130
         05 WS-NUM-MONTH              PIC 9(2).                         00702230
         05 WS-NUM-DAY                PIC 9(2).                         00702330
                                                                        00702430
                                                                        00703006
       PROCEDURE DIVISION.                                              00710004
                                                                        00720004
           PERFORM OPEN-CURSOR                                          00730004
                                                                        00731029
           PERFORM UNTIL SQLCODE NOT = 0                                00741024
              PERFORM INSERT-PAYMENT-PLAN                               00750030
           END-PERFORM                                                  00780004
                                                                        00790004
           PERFORM CLOSE-CURSOR                                         00810021
           STOP RUN                                                     00820004
           .                                                            00830004
                                                                        00840004
       OPEN-CURSOR.                                                     00850004
                                                                        00860004
           EXEC SQL                                                     00870004
              OPEN C1                                                   00880004
           END-EXEC                                                     00890004
           .                                                            00920004
                                                                        00930004
                                                                        01110004
       LOAN-STATUS-CHECK.                                               01111030
           DISPLAY 'YAY'                                                01112030
           .                                                            01113030
                                                                        01120004
       INSERT-PAYMENT-PLAN.                                             01130030
                                                                        01130123
           EXEC SQL                                                     01130230
              FETCH C1                                                  01130430
               INTO :LOAN_LOAN-ID                                       01130530
                  , :LOAN_CUSTOMER-ID                                   01130630
                  , :LOAN_TYPE-ID                                       01130730
                  , :LOAN_LOAN-AMOUNT                                   01130830
                  , :LOAN_LOAN-STATUS                                   01130930
                  , :LOAN_INTEREST-RATE                                 01131030
                  , :LOAN_INTEREST-TYPE                                 01131130
                  , :LOAN_CREATION-DATE                                 01131230
                  , :LOAN_DOWN-PAYMENT                                  01131330
                  , :LOAN_PAYMENT-PERIOD                                01131430
           END-EXEC                                                     01131630
                                                                        01131730
           IF SQLCODE = 0                                               01131830
              MOVE LOAN_LOAN-ID TO PLAN_LOAN-ID                         01131930
              MOVE LOAN_LOAN-AMOUNT TO PLAN_REMAINING-LOAN              01132030
              MOVE LOAN_LOAN-AMOUNT TO WS-TOTAL-LOAN                    01132130
              MOVE LOAN_CREATION-DATE TO PLAN_DUE-DATE                  01132230
              MOVE LOAN_INTEREST-RATE TO PLAN_INTEREST-RATE             01132330
              MOVE LOAN_PAYMENT-PERIOD TO WS-PAYMENT-PERIOD             01132430
              DISPLAY 'MOVE COMPLETE'                                   01132530
                                                                        01132623
      ******************************************************            01132730
      * COMPUTE THE PRINCIPAL AND INTEREST RATE IN DECIMAL *            01132830
      ******************************************************            01132930
                                                                        01133030
           COMPUTE WS-PRINCIPAL                                         01133130
           = WS-TOTAL-LOAN / WS-PAYMENT-PERIOD                          01133230
                                                                        01133330
           COMPUTE WS-INTEREST-DECIMAL                                  01133430
           = PLAN_INTEREST-RATE / 100                                   01133530
                                                                        01133630
      * SET THE CREATION DATE FOR MONTH UPDATE                          01133730
           MOVE PLAN_DUE-DATE(1:4) TO WS-NUM-YEAR                       01133830
           MOVE PLAN_DUE-DATE(6:2) TO WS-NUM-MONTH                      01133930
           MOVE PLAN_DUE-DATE(9:2) TO WS-NUM-DAY                        01134030
                                                                        01134130
           PERFORM VARYING WS-COUNT FROM 1 BY 1                         01134230
              UNTIL WS-COUNT > WS-PAYMENT-PERIOD                        01134330
                                                                        01134430
              COMPUTE PLAN_REMAINING-LOAN                               01134530
              = PLAN_REMAINING-LOAN - WS-PRINCIPAL                      01134630
                                                                        01134730
              COMPUTE WS-MULTIPLIER ROUNDED                             01134830
              = 1 + (WS-PAYMENT-PERIOD * WS-INTEREST-DECIMAL / 2)       01134930
              + ((WS-PAYMENT-PERIOD * WS-INTEREST-DECIMAL) ** 2 / 12)   01135030
                                                                        01135130
              COMPUTE PLAN_PAYMENT-AMOUNT ROUNDED                       01135230
                   = WS-PRINCIPAL * WS-MULTIPLIER                       01135330
                                                                        01135430
              MOVE PLAN_PAYMENT-AMOUNT TO PLAN_REMAINING-AMOUNT         01135530
              IF WS-NUM-MONTH = 12                                      01136430
                 ADD 1 TO WS-NUM-YEAR                                   01136530
                 MOVE 1 TO WS-NUM-MONTH                                 01136630
              ELSE                                                      01136730
                 ADD 1 TO WS-NUM-MONTH                                  01136830
              END-IF                                                    01137030
                                                                        01137130
              MOVE WS-NUM-YEAR TO PLAN_DUE-DATE(1:4)                    01137230
              MOVE WS-NUM-MONTH TO PLAN_DUE-DATE(6:2)                   01137330
                                                                        01137530
              DISPLAY 'LOAN-ID: ' PLAN_LOAN-ID                          01137630
              DISPLAY 'DUE-DATE: ' PLAN_DUE-DATE                        01137730
              DISPLAY 'PRINCIPAL AMOUNT: ' WS-PRINCIPAL                 01137830
              DISPLAY 'PAYMENT AMOUNT: ' PLAN_PAYMENT-AMOUNT            01137930
              DISPLAY 'REMAINING AMOUNT: ' PLAN_REMAINING-AMOUNT        01138030
              DISPLAY 'REMAINING LOAN: ' PLAN_REMAINING-LOAN            01138130
              DISPLAY 'INTEREST RATE: ' PLAN_INTEREST-RATE              01138230
              DISPLAY '-----------------------'                         01138330
                                                                        01138430
                                                                        01138530
              EXEC SQL                                                  01138630
                INSERT INTO PAYPLAN                                     01138731
                   (LOAN_ID, DUE_DATE, PAYMENT_AMOUNT,                  01138830
                    REMAINING_AMOUNT, REMAINING_LOAN, INTEREST_RATE)    01138930
                 VALUES                                                 01139030
                  (:PLAN_LOAN-ID, :PLAN_DUE-DATE, :PLAN_PAYMENT-AMOUNT, 01139130
                    :PLAN_REMAINING-AMOUNT, :PLAN_REMAINING-LOAN,       01139230
                    :PLAN_INTEREST-RATE)                                01139330
              END-EXEC                                                  01139430
                                                                        01139530
           END-PERFORM                                                  01139630
                                                                        01139730
                                                                        01139828
           IF SQLCODE = 0                                               01139930
              DISPLAY 'PAYMENT PLAN INSERTED'                           01140030
           END-IF                                                       01140123
                                                                        01140223
           .                                                            01141023
                                                                        01150023
                                                                        01241030
       CLOSE-CURSOR.                                                    01250014
           EXEC SQL                                                     01251014
             CLOSE C1                                                   01252014
           END-EXEC                                                     01253014
                                                                        01254014
           .                                                            01260014
                                                                        01270011
