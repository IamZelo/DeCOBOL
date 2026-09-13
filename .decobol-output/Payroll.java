import java.math.BigDecimal;
import java.math.RoundingMode;
/**
 * Generated from COBOL program PAYROLL by DeCOBOL.
 *
 * This is a deterministic skeleton: field types and storage semantics come
 * from the PIC clauses below, but paragraph bodies are TODO stubs. The
 * converter agent fills them in from PAYROLL's PROCEDURE DIVISION;
 * this class is what it falls back to if that step is unavailable.
 */
public class Payroll {
    // WS-EMP-NAME: PIC X(20) USAGE DISPLAY
    private String wsEmpName = " ".repeat(20);
    // WS-EMP-COUNT: PIC 9(3) USAGE DISPLAY
    private int wsEmpCount = 0;
    // WS-HOURS-WORKED: PIC 9(3)V9(2) USAGE DISPLAY
    private BigDecimal wsHoursWorked = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-HOURLY-RATE: PIC S9(5)V99 USAGE COMP-3
    private BigDecimal wsHourlyRate = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-GROSS-PAY: PIC S9(7)V99 USAGE COMP-3
    private BigDecimal wsGrossPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    // WS-TAX-RATE: PIC V999 USAGE DISPLAY
    private BigDecimal wsTaxRate = BigDecimal.ZERO.setScale(3, RoundingMode.HALF_UP);
    // WS-NET-PAY: PIC S9(7)V99 USAGE COMP-3
    private BigDecimal wsNetPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    /**
     * COBOL paragraph MAIN-PARA (no section),
     * lines 15-23.
     */
    private void mainPara() {
        // TODO: translate this paragraph's COBOL body.
        /*
    MOVE "JANE DOE" TO WS-EMP-NAME.
    MOVE 40.00 TO WS-HOURS-WORKED.
    MOVE 25.50 TO WS-HOURLY-RATE.
    COMPUTE WS-GROSS-PAY ROUNDED = WS-HOURS-WORKED * WS-HOURLY-RA
    COMPUTE WS-NET-PAY ROUNDED = WS-GROSS-PAY * (1 - WS-TAX-RATE)
    MOVE 12345 TO WS-EMP-COUNT.
    DISPLAY WS-EMP-NAME.
    STOP RUN.
        */
    }
    public static void main(String[] args) {
        Payroll program = new Payroll();
        // TODO: invoke the entry paragraph.
    }
}
