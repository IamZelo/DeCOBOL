package com.legacy.bank.refactored;

import java.math.BigDecimal;
import java.math.RoundingMode;

public class Payroll {
    private String wsEmpName = fitAlphanumeric("                    ", 20);
    private int wsEmpCount = 0;
    private BigDecimal wsHoursWorked = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    private BigDecimal wsHourlyRate = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    private BigDecimal wsGrossPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);
    private BigDecimal wsTaxRate = BigDecimal.ZERO.setScale(3, RoundingMode.HALF_UP);
    private BigDecimal wsNetPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP);

    public static void main(String[] args) {
        Payroll p = new Payroll();
        p.wsEmpName = "JANE DOE" + "                    ".substring(0, 20 - "JANE DOE".length());
        p.wsHoursWorked = new BigDecimal("40.00").setScale(2, RoundingMode.HALF_UP);
        p.wsHourlyRate = new BigDecimal("25.50").setScale(2, RoundingMode.HALF_UP);
        p.wsGrossPay = p.wsHoursWorked.multiply(p.wsHourlyRate);
        p.wsNetPay = p.wsGrossPay.multiply(BigDecimal.ONE.subtract(p.wsTaxRate));
        p.wsEmpCount = 12345;
        System.out.println(p.wsEmpName);
    }

    /**
     * COBOL alphanumeric MOVE semantics for PIC X(n): right-pad with spaces
     * to {@code length}, truncate on the right when the value is longer.
     */
    private static String fitAlphanumeric(String value, int length) {
        if (value == null) {
            value = "";
        }
        if (value.length() > length) {
            return value.substring(0, length);
        }
        return String.format("%-" + length + "s", value);
    }
}