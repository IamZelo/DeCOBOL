package com.legacy.bank.refactored;
/**
 * Generated from COBOL program PAYMENT by DeCOBOL.
 *
 * This is a deterministic skeleton: field types and storage semantics come
 * from the PIC clauses below, but paragraph bodies are TODO stubs. The
 * converter agent fills them in from PAYMENT's PROCEDURE DIVISION;
 * this class is what it falls back to if that step is unavailable.
 */
public class Payment {
    // DATA-RECORDS: PIC X(80) USAGE DISPLAY
    private String dataRecords = " ".repeat(80);
    // FS-INFILE: PIC X(02) USAGE DISPLAY
    private String fsInfile = " ".repeat(2);
    // EOF: PIC X USAGE DISPLAY
    private String eof = " ";
    // READ-CNTR: PIC 9(03) USAGE DISPLAY
    private int readCntr = 0;
    // OK-CNTR: PIC 9 USAGE DISPLAY
    private int okCntr = 0;
    // ERR-CNTR: PIC 9 USAGE DISPLAY
    private int errCntr = 0;
    // INS-CNTR: PIC 9 USAGE DISPLAY
    private int insCntr = 0;
    // CHAR-CNTR: PIC 9(2) USAGE DISPLAY
    private int charCntr = 0;
    // ERR-FLAG: PIC 9 USAGE DISPLAY
    private int errFlag = 0;
    // WS-DATE-YYYY: PIC X(4) USAGE DISPLAY
    private String wsDateYyyy = " ".repeat(4);
    // WS-DATE-MM: PIC X(2) USAGE DISPLAY
    private String wsDateMm = " ".repeat(2);
    // WS-DATE-DD: PIC X(2) USAGE DISPLAY
    private String wsDateDd = " ".repeat(2);
    // WS-DATE-GENERATED: PIC X(30) USAGE DISPLAY
    private String wsDateGenerated = " ".repeat(30);
    // WS-DATE-GENERATED-LINE: PIC X(50) USAGE DISPLAY
    private String wsDateGeneratedLine = " ".repeat(50);
    // WS-DATE-FOR-CALC: PIC X(10) USAGE DISPLAY
    private String wsDateForCalc = " ".repeat(10);
    // MOVE-FLAG: PIC 9 USAGE DISPLAY
    private int moveFlag = 0;
    // ERR-MESSAGE: PIC X(20) USAGE DISPLAY
    private String errMessage = " ".repeat(20);
    // ERR-P-ID: PIC X(15) USAGE DISPLAY
    private String errPId = " ".repeat(15);
    // ERR-I-ID: PIC X(15) USAGE DISPLAY
    private String errIId = " ".repeat(15);
    // ERR-AMT: PIC X(15) USAGE DISPLAY
    private String errAmt = " ".repeat(15);
    // ERR-DATE: PIC X(15) USAGE DISPLAY
    private String errDate = " ".repeat(15);
    // ERR-UNKNOWN: PIC X(20) USAGE DISPLAY
    private String errUnknown = " ".repeat(20);
    // ERR-REASON: PIC X(20) USAGE DISPLAY
    private String errReason = " ".repeat(20);
    /**
     * COBOL paragraph 000-MAIN (000-MAIN),
     * lines 103-122.
     * Performs: 001-FETCH-DATE, 100-OPEN-FILE, 200-READ-RECORDS, 210-ERROR-CONTROL, 500-CLOSE-FILE
     */
    private void p000Main() {
        // TODO: translate this paragraph's COBOL body.
        /*
    DISPLAY "PAYMENT PROGRAM."
    DISPLAY "SQL CODE IS: " SQLCODE

    PERFORM 001-FETCH-DATE
    PERFORM 100-OPEN-FILE
    PERFORM UNTIL EOF = "Y"
       PERFORM 200-READ-RECORDS
         IF EOF = "N" THEN
            PERFORM 210-ERROR-CONTROL
         ELSE
            CONTINUE
         END-IF
    END-PERFORM
    PERFORM 500-CLOSE-FILE

    STOP RUN.
        */
    }
    /**
     * COBOL paragraph 001-FETCH-DATE (001-FETCH-DATE),
     * lines 123-142.
     */
    private void p001FetchDate() {
        // TODO: translate this paragraph's COBOL body.
        /*
 FETCHING CURRENT DATE.

    ACCEPT WS-CURRENT-DATE FROM DATE YYYYMMDD

    STRING WS-DATE-DD "-" WS-DATE-MM "-" WS-DATE-YYYY
       DELIMITED BY SIZE
       INTO WS-DATE-GENERATED

    STRING "GENERATED ON: " DELIMITED BY SIZE
           WS-DATE-GENERATED DELIMITED BY SIZE
      INTO WS-DATE-GENERATED-LINE

    STRING WS-DATE-YYYY "-" WS-DATE-MM "-" WS-DATE-DD
      DELIMITED BY SIZE
      INTO WS-DATE-FOR-CALC

    DISPLAY WS-DATE-FOR-CALC " DATE FOR CALC.".
        */
    }
    /**
     * COBOL paragraph 100-OPEN-FILE (100-OPEN-FILE),
     * lines 143-155.
     */
    private void p100OpenFile() {
        // TODO: translate this paragraph's COBOL body.
        /*
 OPENING THE INFILE.

    OPEN INPUT PAYIN
    IF FS-INFILE NOT = "00"
       DISPLAY "ERROR OPENING THE INFILE PAYIN."
       DISPLAY "FILE STATUS CODE: " FS-INFILE
       STOP RUN
    ELSE
       CONTINUE
    END-IF.
        */
    }
    /**
     * COBOL paragraph 200-READ-RECORDS (200-READ-RECORDS),
     * lines 156-170.
     */
    private void p200ReadRecords() {
        // TODO: translate this paragraph's COBOL body.
        /*
 READING RECORDS FROM THE INFILE INTO THE VAR. COPYBOOK.

    READ PAYIN INTO PAYMENT-DETAILS
       AT END
          MOVE "Y" TO EOF
          DISPLAY " "
          DISPLAY "REACHED END OF FILE."
          DISPLAY "SQLCODE IS: " SQLCODE
       NOT AT END
          DISPLAY " "
          ADD 1 TO READ-CNTR
    END-READ.
        */
    }
    /**
     * COBOL paragraph 210-ERROR-CONTROL (210-ERROR-CONTROL),
     * lines 171-199.
     * Performs: 299-ERROR-DISPLAY, 300-MOVE-DATA
     */
    private void p210ErrorControl() {
        // TODO: translate this paragraph's COBOL body.
        /*
 SECTION. CONTROLLING RECORDS FOR ERRORS.

 CONTROLLING PAYMENT ID FOR ERRORS.

    INITIALIZE ERR-CNTR
    INITIALIZE OK-CNTR

    EVALUATE TRUE
       WHEN PAYMENT-ID = SPACES
          MOVE 1 TO ERR-CNTR
          SET ERR-3 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN PAYMENT-ID IS NOT NUMERIC
          MOVE 1 TO ERR-CNTR
          SET ERR-1 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN PAYMENT-ID IS ZERO
          MOVE 1 TO ERR-CNTR
          SET ERR-2 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN OTHER
          MOVE 1 TO OK-CNTR
          ADD 1 TO INS-CNTR
            PERFORM 300-MOVE-DATA
          CONTINUE
    END-EVALUATE.
        */
    }
    /**
     * COBOL paragraph 230-INVOICE-ID-CTRL (210-ERROR-CONTROL),
     * lines 200-226.
     * Performs: 299-ERROR-DISPLAY, 300-MOVE-DATA
     */
    private void p230InvoiceIdCtrl() {
        // TODO: translate this paragraph's COBOL body.
        /*
 CONTROLLING INVOICE ID FOR ERRORS.

    INITIALIZE ERR-CNTR
    INITIALIZE OK-CNTR

    EVALUATE TRUE
       WHEN TERMIN-ID = SPACES
          MOVE 2 TO ERR-CNTR
          SET ERR-3 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN TERMIN-ID IS NOT NUMERIC
          MOVE 2 TO ERR-CNTR
          SET ERR-1 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN TERMIN-ID IS ZERO
          MOVE 2 TO ERR-CNTR
          SET ERR-2 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN OTHER
          MOVE 2 TO OK-CNTR
          ADD 1 TO INS-CNTR
            PERFORM 300-MOVE-DATA
          CONTINUE
    END-EVALUATE.
        */
    }
    /**
     * COBOL paragraph 240-PAID-AMOUNT-CTRL (210-ERROR-CONTROL),
     * lines 227-253.
     * Performs: 299-ERROR-DISPLAY, 300-MOVE-DATA
     */
    private void p240PaidAmountCtrl() {
        // TODO: translate this paragraph's COBOL body.
        /*
 CONTROLLING PAID AMOUNT FOR ERRORS.

    INITIALIZE ERR-CNTR
    INITIALIZE OK-CNTR

    EVALUATE TRUE
       WHEN PAYMENT-ID = SPACES
          MOVE 3 TO ERR-CNTR
          SET ERR-3 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN PAID-AMT IS NOT NUMERIC
          MOVE 3 TO ERR-CNTR
          SET ERR-1 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN PAID-AMT IS NEGATIVE
          MOVE 3 TO ERR-CNTR
          SET ERR-4 TO TRUE
            PERFORM 299-ERROR-DISPLAY
       WHEN OTHER
          MOVE 3 TO OK-CNTR
          ADD 1 TO INS-CNTR
            PERFORM 300-MOVE-DATA
          CONTINUE
    END-EVALUATE.
        */
    }
    /**
     * COBOL paragraph 250-PAID-DATE-CTRL (210-ERROR-CONTROL),
     * lines 254-307.
     * Performs: 299-ERROR-DISPLAY, 300-MOVE-DATA
     */
    private void p250PaidDateCtrl() {
        // TODO: translate this paragraph's COBOL body.
        /*
 CONTROLLING PAID DATE FOR ERRORS.

    INITIALIZE ERR-CNTR
    INITIALIZE OK-CNTR
    INITIALIZE CHAR-CNTR

    INSPECT PAID-DATE
       TALLYING CHAR-CNTR FOR ALL "/", "!", "?", "&", "@",
                                  "%", "(", ")", "*", "_",
                                  "#", "=", "}", "{", "\"

    IF PAID-DATE(1:10) = WS-DATE-FOR-CALC(1:10)
    AND CHAR-CNTR > 0
        MOVE 4 TO ERR-CNTR
        SET ERR-5 TO TRUE
    END-IF

    IF PAID-DATE(1:10) > WS-DATE-FOR-CALC(1:10)
    AND CHAR-CNTR = 0
        MOVE 4 TO ERR-CNTR
        SET ERR-6 TO TRUE
    END-IF

    IF PAID-DATE(1:10) < WS-DATE-FOR-CALC(1:10)
    AND CHAR-CNTR = 0
        MOVE 4 TO ERR-CNTR
        SET ERR-6 TO TRUE
    END-IF

    IF PAID-DATE(1:10) > WS-DATE-FOR-CALC(1:10)
    AND CHAR-CNTR > 0
        MOVE 4 TO ERR-CNTR
        SET ERR-5 TO TRUE
    END-IF

    IF CHAR-CNTR > 0
       MOVE 4 TO ERR-CNTR
       SET ERR-5 TO TRUE
    END-IF

    IF ERR-CNTR = 4
       PERFORM 299-ERROR-DISPLAY
    ELSE
       MOVE 4 TO OK-CNTR
       ADD 1 TO INS-CNTR
         PERFORM 300-MOVE-DATA
       CONTINUE
    END-IF

    INITIALIZE INS-CNTR.
        */
    }
    /**
     * COBOL paragraph 299-ERROR-DISPLAY (299-ERROR-DISPLAY),
     * lines 308-330.
     */
    private void p299ErrorDisplay() {
        // TODO: translate this paragraph's COBOL body.
        /*
 DISPLAYING ERRORS FOUND IN THE INFILE.

    MOVE ERR-CNTR TO ERR-FLAG

    DISPLAY SPACE
    DISPLAY ERR-MESSAGE
    DISPLAY "CURRENT RECORD NUMBER: " READ-CNTR

    EVALUATE ERR-FLAG
      WHEN 1
         DISPLAY ERR-P-ID SPACE PAYMENT-ID SPACE ERR-REASON
      WHEN 2
         DISPLAY ERR-I-ID SPACE TERMIN-ID SPACE ERR-REASON
      WHEN 3
         DISPLAY ERR-AMT SPACE PAID-AMT SPACE ERR-REASON
      WHEN 4
         DISPLAY ERR-DATE SPACE PAID-DATE SPACE ERR-REASON
      WHEN OTHER
         DISPLAY ERR-UNKNOWN
    END-EVALUATE.
        */
    }
    /**
     * COBOL paragraph 300-MOVE-DATA (300-MOVE-DATA),
     * lines 331-360.
     * Performs: 310-INSERT
     */
    private void p300MoveData() {
        // TODO: translate this paragraph's COBOL body.
        /*
 MOVING VALID RECORDS TO DCLGEN HOST VARIABLES.

    MOVE OK-CNTR TO MOVE-FLAG

    DISPLAY SPACE
    DISPLAY "MOVED RECORDS:"
    DISPLAY "CURRENT RECORD NUMBER: " READ-CNTR

    EVALUATE MOVE-FLAG
      WHEN 1
         MOVE PAYMENT-ID TO PAY_PAYMENT-ID
         DISPLAY "PAYMENT ID: " PAYMENT-ID, SPACE PAY_PAYMENT-ID
      WHEN 2
         MOVE TERMIN-ID TO PAY_INVOICE-ID
         DISPLAY "INVOICE ID: " TERMIN-ID, SPACE PAY_INVOICE-ID
      WHEN 3
         MOVE PAID-AMT TO PAY_PAID-AMOUNT
         DISPLAY "PAID AMOUNT: " PAID-AMT, SPACE PAY_PAID-AMOUNT
      WHEN 4
         MOVE PAID-DATE TO PAY_PAID-DATE
         DISPLAY "PAID DATE: " PAID-DATE, SPACE PAY_PAID-DATE
         DISPLAY SPACE
    END-EVALUATE.

    IF INS-CNTR = 4
       PERFORM 310-INSERT
    END-IF.
        */
    }
    /**
     * COBOL paragraph 310-INSERT (310-INSERT),
     * lines 361-385.
     */
    private void p310Insert() {
        // TODO: translate this paragraph's COBOL body.
        /*
 INSERTING VALID ROWS INTO THE TABLE.

    DISPLAY SPACE
    DISPLAY "INSERTING INTO 'PAYMENT' TABLE:"

    IF SQLCODE = 0
       DISPLAY "INSERT WAS SUCCESSFULL. SQLCODE: "
    ELSE
       DISPLAY "SQL ERROR: " SQLCODE
    END-IF.
        */
    }
    /**
     * COBOL paragraph 500-CLOSE-FILE (500-CLOSE-FILE),
     * lines 386-392.
     */
    private void p500CloseFile() {
        // TODO: translate this paragraph's COBOL body.
        /*
 CLOSING THE INFILE.

    CLOSE PAYIN.
        */
    }
    public static void main(String[] args) {
        Payment program = new Payment();
        // TODO: invoke the entry paragraph.
    }
}
