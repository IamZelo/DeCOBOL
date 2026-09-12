import java.math.BigDecimal;
import java.math.RoundingMode;

public class Payroll {
    private String wsEmpName = "                    " ;
    private int wsEmpCount = 0 ;
    private BigDecimal wsHoursWorked = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP) ;
    private BigDecimal wsHourlyRate = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP) ;
    private BigDecimal wsGrossPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP) ;
    private BigDecimal wsTaxRate = BigDecimal.ZERO.setScale(3, RoundingMode.HALF_UP) ;
    private BigDecimal wsNetPay = BigDecimal.ZERO.setScale(2, RoundingMode.HALF_UP) ;

    public static void main(String[] args) {
        Payroll p = new Payroll() ;
        p.pMainPara() ;
    }

    private void pMainPara() {
        this.wsEmpName = String.format("%-20s", "JANE DOE") ;
        this.wsHoursWorked = new BigDecimal("40.00") .setScale(2, RoundingMode.HALF_UP) ;
        this.wsHourlyRate = new BigDecimal("25.50") .setScale(2, RoundingMode.HALF_UP) ;
        this.wsGrossPay = this.wsHoursWorked
                .multiply(this.wsHourlyRate)
                .setScale(2, RoundingMode.HALF_UP) ;
        this.wsTaxRate = new BigDecimal("0.200") .setScale(3, RoundingMode.HALF_UP) ;
        this.wsNetPay = this.wsGrossPay
                .multiply(BigDecimal.ONE.subtract(this.wsTaxRate))
                .setScale(2, RoundingMode.HALF_UP) ;
        this.wsEmpCount = 12345 % 1000 ;
        System.out.println(this.wsEmpName) ;
    }
}