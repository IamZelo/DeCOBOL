       IDENTIFICATION DIVISION.
      *----------------------------------------------------------------
       PROGRAM-ID. LNDWISE4.

       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT WS-OUTFILE-1 ASSIGN TO OUTFILE
               ORGANIZATION IS SEQUENTIAL
               ACCESS MODE IS SEQUENTIAL
               FILE STATUS IS STATUS-OUTFILE1.

       DATA DIVISION.

       FILE SECTION.
       FD WS-OUTFILE-1.
       01  WS-OUTFILE-POST   PIC X(200).

       WORKING-STORAGE SECTION.

      *----------------------------------------------------------------
      * Common runtime info & counters
      *----------------------------------------------------------------
       01  WS-SQL-ACTION           PIC X(40).
       01  WS-SQLCODE-DISPLAY      PIC S9(9) COMP.

       01  WS-CURRENT-DATE.
           05 WS-DATE-YYYY        PIC X(4).
           05 WS-DATE-MM          PIC X(2).
           05 WS-DATE-DD          PIC X(2).

       01  WS-DATE-GENERATED       PIC X(30).
       01  WS-DATE-GENERATED-LINE  PIC X(50).
       01  WS-DATE-FOR-CALC        PIC X(10).

       01  CURRENT-LOAN-ID         PIC S9(9) COMP.

      *----------------------------------------------------------------
      * Output Record Layout
      *----------------------------------------------------------------
       01  WS-HEADER-RECORD        PIC X(200).
      *    'CUST-ID   LOAN-ID    LOAN-STAT PAY-STAT DUE-DATE
      *    '   PAID-DATE  TOT-PAID          INT-PAID
      *    '          PRINCIPAL-LEFT    EXCESS-AMOUNT'.

       01  REPORT-RECORD.

          05 WS-TERM-ID                  PIC 9(9).
          05 FILLER                      PIC X(1).
          05 WS-LOAN-ID                  PIC 9(9).
          05 FILLER                      PIC X(5).
          05 WS-LOAN-STATUS              PIC X(1).
          05 FILLER                      PIC X(8).
          05 WS-NEXT-PAYMENT-STATUS      PIC X(7).
          05 FILLER                      PIC X(2).
          05 WS-NEXT-DUE-DATE            PIC X(10).
          05 FILLER                      PIC X(1).
          05 WS-PREV-DATE-PAID           PIC X(10).
          05 FILLER                      PIC X(1).
          05 WS-ACTUAL-PAID-AMT          PIC +ZZZZZZZZZZZZZZ9.99.
          05 FILLER                      PIC X(1).
          05 WS-TOTAL-INTEREST-EARNED    PIC +ZZZZZZZZZZZZZZ9.99.
          05 FILLER                      PIC X(1).
          05 WS-REMAINING-PRIN-RPT       PIC +ZZZZZZZZZZZZZZ9.99.
          05 FILLER                      PIC X(1).
          05 WS-ACTUAL-PAY-DIFF          PIC +ZZZZZZZZZZZZZZ9.99.

       01 STATUS-OUTFILE1          PIC X(2).
       01 WS-RETURN-CODE           PIC S9(4) COMP.

      *----------------------------------------------------------------
      * Variables for payment and leftover calculations
      *----------------------------------------------------------------
       01  LEFTOVER-PAYMENT        PIC S9(15)V9(2) COMP-3.
       01  EXCESS-PAYMENT          PIC S9(15)V9(2) COMP-3.
       01  EXCESS-LOAN-PAYMENT     PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  TOT-EXCESS-PAYMENT      PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  WS-PERIOD-DEC           PIC S9(11)V9(2) COMP-3 VALUE 0.

       01  CURRENT-INVOICE-NUMBER  PIC 9(9).
       01  NUMBER-OF-INVOICES-PAID PIC S9(9) COMP.
       01  WS-NO-INVOICES-PAID     PIC S9(9).
       01  ACCUMULATED-TOT-PAYMENTS PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  ADJUSTED-MONTHLY-PAYMENT PIC S9(15)V9(2) COMP-3 VALUE 0.

      *----------------------------------------------------------------
      * Variables for interest/loan math
      *----------------------------------------------------------------
       01  MONTHLY-INTEREST-RATE   PIC S9(2)V9(2) COMP-3.
       01  REMAINING-PRINCIPAL     PIC S9(15)V9(2) COMP-3.
       01  INTEREST-PAYMENT        PIC S9(15)V9(2) COMP-3.
       01  PRINCIPAL-PAYMENT       PIC S9(15)V9(2) COMP-3.
       01  TOTAL-INTEREST-PAID     PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  TOTAL_PRINCIPAL_PAID    PIC S9(15)V9(2) COMP-3 VALUE 0.

       01  TOTAL_PAYMENT_PAID      PIC S9(15)V9(2) COMP-3.
       01  TOTAL_FULL_PAYMENT      PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  TOTAL_PAYMENT_REMAINING PIC S9(15)V9(2) COMP-3.
       01  TOTAL_POTENTIAL_AMOUNT  PIC S9(15)V9(2) COMP-3 VALUE 0.
       01  ACTUAL-MONEY-TO-BANK    PIC S9(15)V9(2) COMP-3.
       01  TOTAL-EXCESS-AMOUNT     PIC S9(15)V9(2) COMP-3.

      *----------------------------------------------------------------
      * For display/debugging
      *----------------------------------------------------------------
       01  WS-DISPLAY-NUMBER       PIC S9(9) COMP.
       01  WS-TEST-DISPLAY         PIC X(30).
       01  WS-NULL-PAYMENT-DATE    PIC S9(4) COMP VALUE 0.
       01  WS-COUNTER              PIC 9(4).

      *-----------------------------------------------------------------
      * NEW FIELDS FOR CSV
      *-----------------------------------------------------------------
       01  REPORT-CSV-LINE         PIC X(200).
       01  QUPTE-FIELD             PIC X     VALUE """".
       01  COMMA-FIELD             PIC X     VALUE ",".

      *-----------------------------------------------------------------
      * INCLUDE SQL DCLGENS
      *-----------------------------------------------------------------

           EXEC SQL
             INCLUDE SQLCA
           END-EXEC.

           EXEC SQL
             INCLUDE PLAN
           END-EXEC.

           EXEC SQL
             INCLUDE PAYMENT
           END-EXEC.

           EXEC SQL
             INCLUDE LOAN
           END-EXEC.

      *----------------------------------------------------------------
      * Cursor that selects plan lines to process
      *----------------------------------------------------------------
           EXEC SQL
             DECLARE C-UPDATE-PLAN CURSOR WITH HOLD FOR
               SELECT
                PAYPLAN.INVOICE_ID,
                PAYPLAN.LOAN_ID,
                PAYPLAN.DUE_DATE,
                PAYPLAN.PAYMENT_AMOUNT,
                PAYPLAN.PLAN_STATUS,
                PAYPLAN.REMAINING_AMOUNT,
                PAYPLAN.REMAINING_LOAN,
                PAYPLAN.INTEREST_RATE,
                COALESCE(PAYMENT.INVOICE_ID,'0'),
                COALESCE(PAYMENT.PAID_AMOUNT, '0'),
                PAYMENT.PAID_DATE,
                LOAN.CUSTOMER_ID,
                LOAN.LOAN_ID,
                LOAN.LOAN_AMOUNT,
                LOAN.LOAN_STATUS,
                LOAN.PAYMENT_PERIOD,
                LOAN.CREATION_DATE
              FROM   PAYPLAN
              LEFT JOIN PAYMENT
                     ON PAYPLAN.INVOICE_ID = PAYMENT.INVOICE_ID
              JOIN LOAN
                     ON PAYPLAN.LOAN_ID = LOAN.LOAN_ID
              WHERE PAYPLAN.PLAN_STATUS IN ('DUE','PARTIAL','OVERDUE')
              FOR UPDATE OF
                REMAINING_AMOUNT,
                PLAN_STATUS,
                REMAINING_LOAN,
                LOAN_STATUS
           END-EXEC.

       PROCEDURE DIVISION.

      *----------------------------------------------------------------
      * Main Program Flow
      *----------------------------------------------------------------
           PERFORM 500-INITIALIZE-PART2

           PERFORM 600-FETCH-EXPECTED-PAYMENTS
           PERFORM UNTIL SQLCODE NOT = 0
               PERFORM 700-PAYMENT-CHECK
               PERFORM 900-LOAN-TABLE-CHECK
               PERFORM 1000-PROCESS-FOR-WRITING
               PERFORM 600-FETCH-EXPECTED-PAYMENTS
           END-PERFORM

           PERFORM 1200-CLOSE-PART2
           STOP RUN.

      *----------------------------------------------------------------
      * 500-INITIALIZE-PART2
      *----------------------------------------------------------------
       500-INITIALIZE-PART2.
           EXEC SQL
             OPEN C-UPDATE-PLAN
           END-EXEC
           MOVE "OPEN C-UPDATE-PLAN" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           OPEN OUTPUT WS-OUTFILE-1

           ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD

           STRING WS-DATE-YYYY "-" WS-DATE-MM "-" WS-DATE-DD
             DELIMITED BY SIZE
             INTO WS-DATE-GENERATED

           STRING "GENERATED ON: " DELIMITED BY SIZE
                  WS-DATE-GENERATED DELIMITED BY SIZE
             INTO WS-DATE-GENERATED-LINE

           STRING
               'TERM-ID   LOAN-ID    LOAN-STAT   PAY-STAT DUE-DATE '
               DELIMITED BY SIZE
               '  PAID-DATE  TOT-PAID            INT-PAID          '
               DELIMITED BY SIZE
               '  PRINCIPAL-LEFT      EXCESS-AMOUNT    '
               DELIMITED BY SIZE
               INTO WS-HEADER-RECORD.

           WRITE WS-OUTFILE-POST FROM WS-DATE-GENERATED-LINE

           WRITE WS-OUTFILE-POST FROM WS-HEADER-RECORD
           .

      *----------------------------------------------------------------
      * 600-FETCH-EXPECTED-PAYMENTS
      *----------------------------------------------------------------
       600-FETCH-EXPECTED-PAYMENTS.
           EXEC SQL
             FETCH C-UPDATE-PLAN
               INTO :PLAN_INVOICE-ID,
                    :PLAN_LOAN-ID,
                    :PLAN_DUE-DATE,
                    :PLAN_PAYMENT-AMOUNT,
                    :PLAN_PLAN-STATUS,
                    :PLAN_REMAINING-AMOUNT,
                    :PLAN_REMAINING-LOAN,
                    :PLAN_INTEREST-RATE,

                    :PAY_INVOICE-ID,
                    :PAY_PAID-AMOUNT,
                    :PAY_PAID-DATE:WS-NULL-PAYMENT-DATE,

                    :LOAN_CUSTOMER-ID,
                    :LOAN_LOAN-ID,
                    :LOAN_LOAN-AMOUNT,
                    :LOAN_LOAN-STATUS,
                    :LOAN_PAYMENT-PERIOD,
                    :LOAN_CREATION-DATE
           END-EXEC

           MOVE "FETCH C-UPDATE-PLAN" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           DISPLAY PLAN_INVOICE-ID
           DISPLAY PLAN_LOAN-ID
           DISPLAY PLAN_DUE-DATE
           DISPLAY PLAN_PAYMENT-AMOUNT
           DISPLAY PLAN_PLAN-STATUS
           DISPLAY PLAN_REMAINING-AMOUNT
           DISPLAY PLAN_REMAINING-LOAN
           DISPLAY PLAN_INTEREST-RATE

           DISPLAY PAY_PAID-AMOUNT
           DISPLAY PAY_PAID-DATE

           DISPLAY LOAN_CUSTOMER-ID
           DISPLAY LOAN_LOAN-ID
           DISPLAY LOAN_LOAN-STATUS
           DISPLAY LOAN_PAYMENT-PERIOD
           DISPLAY LOAN_CREATION-DATE
           .

      *----------------------------------------------------------------
      * 700-PAYMENT-CHECK
      *----------------------------------------------------------------
       700-PAYMENT-CHECK.
           EVALUATE TRUE
             WHEN PAY_PAID-AMOUNT > 0
               PERFORM 720-PAYMENT-FOUND-CALC
             WHEN PAY_PAID-AMOUNT = 0
               PERFORM 740-PAYMENT-NOT-FOUND
             WHEN OTHER
               MOVE "PAYMENT CHECK" TO WS-SQL-ACTION
               PERFORM CHECK-SQLCODE
           END-EVALUATE
           .

      *----------------------------------------------------------------
      * 720-PAYMENT-FOUND-CALC
      *----------------------------------------------------------------
       720-PAYMENT-FOUND-CALC.
           COMPUTE LEFTOVER-PAYMENT =
                     PLAN_REMAINING-AMOUNT - PAY_PAID-AMOUNT

           EVALUATE TRUE
             WHEN LEFTOVER-PAYMENT > 0
               MOVE 'PARTIAL' TO PLAN_PLAN-STATUS
               PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS

             WHEN LEFTOVER-PAYMENT = 0
               MOVE 'PAID' TO PLAN_PLAN-STATUS
               PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS

             WHEN LEFTOVER-PAYMENT < 0
               MOVE 'PAID' TO PLAN_PLAN-STATUS
               MOVE 0 TO PLAN_REMAINING-AMOUNT
               PERFORM 760-OVERPAYMENT-SUBROUTINE
           END-EVALUATE
           .

      *----------------------------------------------------------------
      * 760-OVERPAYMENT-SUBROUTINE
      *----------------------------------------------------------------
       760-OVERPAYMENT-SUBROUTINE.
           PERFORM OPEN-OVERPAYMENT-CURSOR

           PERFORM UNTIL SQLCODE NOT = 0
               PERFORM 01-OVERPAYMENT-UPDATE
               PERFORM 02-OVERPAYMENT-PROCESSING
           END-PERFORM

           PERFORM CLOSE-OVERPAYMENT-CURSOR
           EXIT
           .

      *----------------------------------------------------------------
      * 01-OVERPAYMENT-UPDATE
      *----------------------------------------------------------------
       01-OVERPAYMENT-UPDATE.
           DISPLAY 'CURRENT LOAN ID ' PLAN_LOAN-ID
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID
           DISPLAY 'STATUS WILL UPDATE TO ' PLAN_PLAN-STATUS

           EXEC SQL
             UPDATE PAYPLAN
                SET REMAINING_AMOUNT = :PLAN_REMAINING-AMOUNT,
                    PLAN_STATUS      = :PLAN_PLAN-STATUS
              WHERE INVOICE_ID = :PLAN_INVOICE-ID
           END-EXEC
           MOVE "UPDATE FOR OVERPAYMENT" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           COMPUTE EXCESS-PAYMENT = LEFTOVER-PAYMENT * (-1)

           .

      *----------------------------------------------------------------
      * OPEN-OVERPAYMENT-CURSOR
      *----------------------------------------------------------------
       OPEN-OVERPAYMENT-CURSOR.
           DISPLAY 'CURRENT LOAN ID ' PLAN_LOAN-ID
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID

           EXEC SQL
             DECLARE C-OVERPAY CURSOR WITH HOLD FOR
               SELECT INVOICE_ID,
                      PAYMENT_AMOUNT,
                      PLAN_STATUS,
                      REMAINING_AMOUNT,
                      DUE_DATE
                 FROM PAYPLAN
                WHERE LOAN_ID    = :PLAN_LOAN-ID
                  AND INVOICE_ID > :PLAN_INVOICE-ID
                  AND PLAN_STATUS IN ('DUE','PARTIAL','OVERDUE')
                ORDER BY DUE_DATE
           END-EXEC.

           EXEC SQL
             OPEN C-OVERPAY
           END-EXEC
           MOVE "OPEN C-OVERPAY" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           DISPLAY 'CURRENT LOAN ID ' CURRENT-LOAN-ID
           DISPLAY 'INVOICE ID ' PLAN_INVOICE-ID
           .

      *----------------------------------------------------------------
      * 02-OVERPAYMENT-PROCESSING
      *----------------------------------------------------------------
       02-OVERPAYMENT-PROCESSING.
           EXEC SQL
             FETCH C-OVERPAY
               INTO :PLAN_INVOICE-ID,
                    :PLAN_PAYMENT-AMOUNT,
                    :PLAN_PLAN-STATUS,
                    :PLAN_REMAINING-AMOUNT,
                    :PLAN_DUE-DATE
           END-EXEC
           MOVE "FETCH C-OVERPAY" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           EVALUATE TRUE
             WHEN SQLCODE = 100
               MOVE EXCESS-PAYMENT TO EXCESS-LOAN-PAYMENT
               EXIT
             WHEN OTHER
               PERFORM 02A-OVERPAYMENT-CALCULATIONS
           END-EVALUATE
           .

      *----------------------------------------------------------------
      * 02A-OVERPAYMENT-CALCULATIONS
      *----------------------------------------------------------------
       02A-OVERPAYMENT-CALCULATIONS.
           COMPUTE LEFTOVER-PAYMENT =
                     PLAN_REMAINING-AMOUNT - EXCESS-PAYMENT

           MOVE LEFTOVER-PAYMENT TO PLAN_REMAINING-AMOUNT

           DISPLAY 'LEFTOVER-PAYMENT AT ' PLAN_INVOICE-ID ' IS '
                   LEFTOVER-PAYMENT ' READ AT PARA 03'

           EVALUATE TRUE
             WHEN LEFTOVER-PAYMENT = PLAN_PAYMENT-AMOUNT
               EXIT
             WHEN LEFTOVER-PAYMENT > PLAN_PAYMENT-AMOUNT
               EXIT
             WHEN LEFTOVER-PAYMENT = 0
               MOVE 'PAID'    TO PLAN_PLAN-STATUS

             WHEN LEFTOVER-PAYMENT > 0
               MOVE 'PARTIAL' TO PLAN_PLAN-STATUS

               INITIALIZE LEFTOVER-PAYMENT
             WHEN LEFTOVER-PAYMENT < 0
               MOVE 'PAID'    TO PLAN_PLAN-STATUS

               MOVE 0         TO PLAN_REMAINING-AMOUNT
           END-EVALUATE
           .

      *----------------------------------------------------------------
      * CLOSE-OVERPAYMENT-CURSOR
      *----------------------------------------------------------------
       CLOSE-OVERPAYMENT-CURSOR.
           EXEC SQL
             CLOSE C-OVERPAY
           END-EXEC
           MOVE "CLOSE C-OVERPAY" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE
           .

      *----------------------------------------------------------------
      * 740-PAYMENT-NOT-FOUND
      *----------------------------------------------------------------
       740-PAYMENT-NOT-FOUND.

           STRING WS-DATE-YYYY "-" WS-DATE-MM "-" WS-DATE-DD
             DELIMITED BY SIZE
             INTO WS-DATE-FOR-CALC

           IF PLAN_DUE-DATE(1:10) < WS-DATE-FOR-CALC(1:10)

              EVALUATE TRUE
                WHEN PLAN_PLAN-STATUS NOT = 'PARTIAL'
                  MOVE 'OVERDUE' TO PLAN_PLAN-STATUS
                  MOVE PLAN_PAYMENT-AMOUNT TO LEFTOVER-PAYMENT
                  PERFORM 800-UPDATE-PAYMENT-PLAN-STATUS
                WHEN PLAN_PLAN-STATUS = 'PARTIAL'
                  EXIT
              END-EVALUATE
           END-IF

           INITIALIZE LEFTOVER-PAYMENT
           .

      *----------------------------------------------------------------
      * 800-UPDATE-PAYMENT-PLAN-STATUS
      *----------------------------------------------------------------
       800-UPDATE-PAYMENT-PLAN-STATUS.
           EXEC SQL
             UPDATE PAYPLAN
                SET REMAINING_AMOUNT = :LEFTOVER-PAYMENT,
                    PLAN_STATUS      = :PLAN_PLAN-STATUS
              WHERE INVOICE_ID = :PLAN_INVOICE-ID
           END-EXEC

           MOVE "UPDATE PAYMENT PLAN TABLE" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE
           .

      *----------------------------------------------------------------
      * 900-LOAN-TABLE-CHECK
      *----------------------------------------------------------------
       900-LOAN-TABLE-CHECK.
           EXEC SQL
             SELECT COUNT(DISTINCT P.INVOICE_ID),
                    SUM(P.PAID_AMOUNT)
               INTO :NUMBER-OF-INVOICES-PAID,
                    :ACCUMULATED-TOT-PAYMENTS
               FROM PAYMENT P
               JOIN PAYPLAN PPS
                  ON P.INVOICE_ID = PPS.INVOICE_ID
              WHERE PPS.LOAN_ID = :PLAN_LOAN-ID
           END-EXEC

           MOVE "FINDING NUMBER OF INSTALLMENTS PAID
      -         "AND SUM OF PAYMENTS"
                 TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           MOVE NUMBER-OF-INVOICES-PAID TO WS-NO-INVOICES-PAID

           COMPUTE ADJUSTED-MONTHLY-PAYMENT =
                   ACCUMULATED-TOT-PAYMENTS / WS-NO-INVOICES-PAID

           COMPUTE MONTHLY-INTEREST-RATE =
                   (PLAN_INTEREST-RATE / 12)

           MOVE LOAN_LOAN-AMOUNT TO REMAINING-PRINCIPAL

           PERFORM VARYING WS-COUNTER FROM 1 BY 1
                   UNTIL WS-COUNTER > WS-NO-INVOICES-PAID

               COMPUTE INTEREST-PAYMENT =
                        (REMAINING-PRINCIPAL * MONTHLY-INTEREST-RATE)
                        / 100

               COMPUTE PRINCIPAL-PAYMENT =
                        ADJUSTED-MONTHLY-PAYMENT - INTEREST-PAYMENT

               COMPUTE REMAINING-PRINCIPAL =
                       REMAINING-PRINCIPAL - PRINCIPAL-PAYMENT

               ADD INTEREST-PAYMENT   TO TOTAL-INTEREST-PAID
               ADD PRINCIPAL-PAYMENT  TO TOTAL_PRINCIPAL_PAID

           END-PERFORM

           COMPUTE TOTAL_POTENTIAL_AMOUNT =
                  (WS-NO-INVOICES-PAID * PLAN_PAYMENT-AMOUNT)

           COMPUTE ACTUAL-MONEY-TO-BANK =
                   TOTAL-INTEREST-PAID + TOTAL_PRINCIPAL_PAID

           COMPUTE TOTAL-EXCESS-AMOUNT =
                   TOTAL_POTENTIAL_AMOUNT - ACTUAL-MONEY-TO-BANK

           COMPUTE TOT-EXCESS-PAYMENT = REMAINING-PRINCIPAL * (-1)

           MOVE REMAINING-PRINCIPAL TO TOTAL_PAYMENT_REMAINING

           DISPLAY 'CURRENT-INVOICE-NUMBER '    CURRENT-INVOICE-NUMBER
           DISPLAY 'WS-NO-INVOICES-PAID  '      WS-NO-INVOICES-PAID
           DISPLAY 'INTEREST-PAYMENT '          INTEREST-PAYMENT
           DISPLAY 'TOTAL-INTEREST-PAID '       TOTAL-INTEREST-PAID
           DISPLAY 'PRINCIPAL-PAYMENT '         PRINCIPAL-PAYMENT
           DISPLAY 'REMAINING-PRINCIPAL '       REMAINING-PRINCIPAL
           DISPLAY 'TOTAL_PAYMENT_PAID '        TOTAL_PAYMENT_PAID
           DISPLAY 'TOTAL_FULL_PAYMENT '        TOTAL_FULL_PAYMENT
           DISPLAY 'TOTAL_PAYMENT_REMAINING '   TOTAL_PAYMENT_REMAINING

           EVALUATE TRUE
             WHEN REMAINING-PRINCIPAL > 0
               PERFORM 910-LOAN-AMOUNT-UPDATE
             WHEN REMAINING-PRINCIPAL = 0
               PERFORM 920-LOAN-DELETE
             WHEN REMAINING-PRINCIPAL < 0
               PERFORM 920-LOAN-DELETE
           END-EVALUATE
           .

      *----------------------------------------------------------------
      * 910-LOAN-AMOUNT-UPDATE
      *----------------------------------------------------------------
       910-LOAN-AMOUNT-UPDATE.
           EXEC SQL
             UPDATE PAYPLAN
                SET REMAINING_LOAN = :REMAINING-PRINCIPAL
              WHERE INVOICE_ID = :PLAN_INVOICE-ID
           END-EXEC
           MOVE "UPDATE TOTAL LOAN-AMOUNT" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE
           .

      *----------------------------------------------------------------
      * 920-LOAN-DELETE
      *----------------------------------------------------------------
       920-LOAN-DELETE.
           MOVE 'C' TO LOAN_LOAN-STATUS

           EXEC SQL
             UPDATE LOAN
                SET LOAN_STATUS = :LOAN_LOAN-STATUS
              WHERE LOAN_ID    = :PLAN_LOAN-ID
           END-EXEC
           MOVE "UPDATE LOAN STATUS" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

      ***  MOVE EXCESS-LOAN-PAYMENT TO WS-EXCESS-AMT

           EXEC SQL
             DELETE FROM PAYPLAN
              WHERE LOAN_ID = :PLAN_LOAN-ID
           END-EXEC
           MOVE "DELETE CURRENT PLAN FOR LOAN" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE
           .

      *----------------------------------------------------------------
      * 1000-PROCESS-FOR-WRITING
      *----------------------------------------------------------------
       1000-PROCESS-FOR-WRITING.


      * Move basic fields into the existing layout
           MOVE PLAN_INVOICE-ID     TO WS-TERM-ID
           MOVE LOAN_LOAN-ID        TO WS-LOAN-ID
           MOVE LOAN_LOAN-STATUS    TO WS-LOAN-STATUS
           MOVE PLAN_PLAN-STATUS    TO WS-NEXT-PAYMENT-STATUS
           MOVE PLAN_DUE-DATE       TO WS-NEXT-DUE-DATE
           MOVE PAY_PAID-DATE       TO WS-PREV-DATE-PAID

      * Also move the newly needed totals
           MOVE ACTUAL-MONEY-TO-BANK      TO WS-ACTUAL-PAID-AMT
           MOVE TOTAL-INTEREST-PAID       TO WS-TOTAL-INTEREST-EARNED
           MOVE REMAINING-PRINCIPAL       TO WS-REMAINING-PRIN-RPT
           MOVE TOTAL-EXCESS-AMOUNT       TO WS-ACTUAL-PAY-DIFF


           EVALUATE TRUE
             WHEN PLAN_PLAN-STATUS = 'PARTIAL' OR 'OVERDUE'
               WRITE WS-OUTFILE-POST FROM REPORT-RECORD
             WHEN LOAN_LOAN-STATUS = 'C'
               WRITE WS-OUTFILE-POST FROM REPORT-RECORD
           END-EVALUATE

           .

      *----------------------------------------------------------------
      * 1200-CLOSE-PART2
      *----------------------------------------------------------------
       1200-CLOSE-PART2.
           EXEC SQL
             CLOSE C-UPDATE-PLAN
           END-EXEC
           MOVE "CLOSE C-PLAN CURSOR" TO WS-SQL-ACTION
           PERFORM CHECK-SQLCODE

           CLOSE WS-OUTFILE-1
           .

      *----------------------------------------------------------------
      * CHECK-SQLCODE
      *    Common routine to handle SQL statuses
      *----------------------------------------------------------------
       CHECK-SQLCODE.
           MOVE SQLCODE TO WS-SQLCODE-DISPLAY
           EVALUATE SQLCODE
             WHEN 0
               DISPLAY "SUCCESSFUL SQL ACTION: " WS-SQL-ACTION
             WHEN 100
               DISPLAY "NO ROWS FOR SQL ACTION: " WS-SQL-ACTION
             WHEN OTHER
               DISPLAY "ABEND DUE TO SQL ERROR DURING: " WS-SQL-ACTION
               DISPLAY "SQLCODE=" WS-SQLCODE-DISPLAY
               DISPLAY "SQL STATE " SQLSTATE
               PERFORM ABEND-PARA
           END-EVALUATE
           EXIT.

      *----------------------------------------------------------------
      * ABEND-PARA
      *----------------------------------------------------------------
       ABEND-PARA.
           DISPLAY "ABEND ACTIVATED"
           MOVE 1111 TO WS-RETURN-CODE
           CALL 'CEE3ABD' USING WS-RETURN-CODE
           GOBACK
           .

      *----------------------------------------------------------------
      * TEST-DISPLAY-PARA
      *----------------------------------------------------------------
       TEST-DISPLAY-PARA.
           DISPLAY WS-TEST-DISPLAY ' ' WS-DISPLAY-NUMBER
           EXIT.

      *----------------------------------------------------------------
      * DESIGN-REPORTS
      *----------------------------------------------------------------
       DESIGN-REPORTS.
           EXIT.
