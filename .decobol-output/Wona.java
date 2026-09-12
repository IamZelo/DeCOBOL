package com.legacy.bank.refactored;
import java.math.BigDecimal;
import java.math.RoundingMode;
/**
 * Generated from COBOL program WONA by DeCOBOL.
 *
 * This is a deterministic skeleton: field types and storage semantics come
 * from the PIC clauses below, but paragraph bodies are TODO stubs. The
 * converter agent fills them in from WONA's PROCEDURE DIVISION;
 * this class is what it falls back to if that step is unavailable.
 */
public class Wona {
    // WS-PAYMENT-PERIOD: PIC 9(9) USAGE DISPLAY
    private int wsPaymentPeriod = 0;
    // WS-MULTIPLIER: PIC 9V9(2) USAGE DISPLAY
    private BigDecimal wsMultiplier = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-INTEREST-DECIMAL: PIC 9V9(4) USAGE DISPLAY
    private BigDecimal wsInterestDecimal = BigDecimal.ZERO.setScale(4, RoundingMode.HALF_UP);
    // WS-PRINCIPAL: PIC 9(15)V9(2) USAGE DISPLAY
    private BigDecimal wsPrincipal = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-COUNT: PIC 99 USAGE DISPLAY
    private int wsCount = 0;
    // WS-TOTAL-LOAN: PIC 9(15)V9(2) USAGE DISPLAY
    private BigDecimal wsTotalLoan = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-NUM-YEAR: PIC 9(4) USAGE DISPLAY
    private int wsNumYear = 0;
    // WS-NUM-MONTH: PIC 9(2) USAGE DISPLAY
    private int wsNumMonth = 0;
    // WS-NUM-DAY: PIC 9(2) USAGE DISPLAY
    private int wsNumDay = 0;
    /**
     * COBOL paragraph OPEN-CURSOR (no section),
     * lines 89-96.
     */
    private void openCursor() {
        // TODO: translate this paragraph's COBOL body.
        /*
    .
        */
    }
    /**
     * COBOL paragraph LOAN-STATUS-CHECK (no section),
     * lines 97-100.
     */
    private void loanStatusCheck() {
        // TODO: translate this paragraph's COBOL body.
        /*
    DISPLAY 'YAY'
    .
        */
    }
    /**
     * COBOL paragraph INSERT-PAYMENT-PLAN (no section),
     * lines 101-194.
     */
    private void insertPaymentPlan() {
        // TODO: translate this paragraph's COBOL body.
        /*
    IF SQLCODE = 0
       MOVE LOAN_LOAN-ID TO PLAN_LOAN-ID
       MOVE LOAN_LOAN-AMOUNT TO PLAN_REMAINING-LOAN
       MOVE LOAN_LOAN-AMOUNT TO WS-TOTAL-LOAN
       MOVE LOAN_CREATION-DATE TO PLAN_DUE-DATE
       MOVE LOAN_INTEREST-RATE TO PLAN_INTEREST-RATE
       MOVE LOAN_PAYMENT-PERIOD TO WS-PAYMENT-PERIOD
       DISPLAY 'MOVE COMPLETE'

*****************************************************
 COMPUTE THE PRINCIPAL AND INTEREST RATE IN DECIMAL *
*****************************************************

    COMPUTE WS-PRINCIPAL
    = WS-TOTAL-LOAN / WS-PAYMENT-PERIOD

    COMPUTE WS-INTEREST-DECIMAL
    = PLAN_INTEREST-RATE / 100

 SET THE CREATION DATE FOR MONTH UPDATE
    MOVE PLAN_DUE-DATE(1:4) TO WS-NUM-YEAR
    MOVE PLAN_DUE-DATE(6:2) TO WS-NUM-MONTH
    MOVE PLAN_DUE-DATE(9:2) TO WS-NUM-DAY

    PERFORM VARYING WS-COUNT FROM 1 BY 1
       UNTIL WS-COUNT > WS-PAYMENT-PERIOD

       COMPUTE PLAN_REMAINING-LOAN
       = PLAN_REMAINING-LOAN - WS-PRINCIPAL

       COMPUTE WS-MULTIPLIER ROUNDED
       = 1 + (WS-PAYMENT-PERIOD * WS-INTEREST-DECIMAL / 2)
       + ((WS-PAYMENT-PERIOD * WS-INTEREST-DECIMAL) ** 2 / 12)

       COMPUTE PLAN_PAYMENT-AMOUNT ROUNDED
            = WS-PRINCIPAL * WS-MULTIPLIER

       MOVE PLAN_PAYMENT-AMOUNT TO PLAN_REMAINING-AMOUNT
       IF WS-NUM-MONTH = 12
          ADD 1 TO WS-NUM-YEAR
          MOVE 1 TO WS-NUM-MONTH
       ELSE
          ADD 1 TO WS-NUM-MONTH
       END-IF

       MOVE WS-NUM-YEAR TO PLAN_DUE-DATE(1:4)
       MOVE WS-NUM-MONTH TO PLAN_DUE-DATE(6:2)

       DISPLAY 'LOAN-ID: ' PLAN_LOAN-ID
       DISPLAY 'DUE-DATE: ' PLAN_DUE-DATE
       DISPLAY 'PRINCIPAL AMOUNT: ' WS-PRINCIPAL
       DISPLAY 'PAYMENT AMOUNT: ' PLAN_PAYMENT-AMOUNT
       DISPLAY 'REMAINING AMOUNT: ' PLAN_REMAINING-AMOUNT
       DISPLAY 'REMAINING LOAN: ' PLAN_REMAINING-LOAN
       DISPLAY 'INTEREST RATE: ' PLAN_INTEREST-RATE
       DISPLAY '-----------------------'

    END-PERFORM

    IF SQLCODE = 0
       DISPLAY 'PAYMENT PLAN INSERTED'
    END-IF

    .
        */
    }
    /**
     * COBOL paragraph CLOSE-CURSOR (no section),
     * lines 195-202.
     */
    private void closeCursor() {
        // TODO: translate this paragraph's COBOL body.
        /*
    .
        */
    }
    public static void main(String[] args) {
        Wona program = new Wona();
        // TODO: invoke the entry paragraph.
    }
}
