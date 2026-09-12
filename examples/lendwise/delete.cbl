       IDENTIFICATION DIVISION.                                         00010000
       PROGRAM-ID. DLTPAYPL.                                            00020002
       AUTHOR. ISURU, WONA & MALENE.                                    00030000
      ********************************************************          00040000
      *      SUBPROGRAM CONNECTED TO "LENDWISE" MAIN PGM.    *          00050000
      *                                                      *          00060000
      * FUNCTION: DELETES ROWS FROM THE TABLE 'PAYPLAN'      *          00070001
      * WHEN THE LOAN HAS BEEN FULLY PAID OFF OR WHEN        *          00080001
      * THE CUSTOMER HAS MOVED THE LOAN TO ANOTHER BANK.     *          00090001
      *                                                      *          00110000
      ********************************************************          00120000
                                                                        00130000
       ENVIRONMENT DIVISION.                                            00140000
       DATA DIVISION.                                                   00150000
       WORKING-STORAGE SECTION.                                         00160000
                                                                        00170000
           EXEC SQL INCLUDE SQLCA    END-EXEC.                          00290003
                                                                        00291005
           EXEC SQL INCLUDE PLAN     END-EXEC.                          00292005
                                                                        00300000
      * FOR CURRENT TIMESTAMP.                                          00310000
       01 DLT-TIMESTAMP    PIC X(26).                                   00311002
                                                                        00320000
       LINKAGE SECTION.                                                 00330000
      * VARIABLES RECIEVED FROM MAIN PROGRAM.                           00340000
                                                                        00350000
       01 LS_LOAN-ID       PIC S9(9) USAGE COMP.                        00360006
                                                                        00390000
                                                                        00410000
       PROCEDURE DIVISION USING LS_LOAN-ID.                             00420002
                                                                        00430000
       MAIN-PARA.                                                       00440000
                                                                        00441000
           DISPLAY "DELETING FROM PAYPLAN."                             00442002
           DISPLAY "LOAN_ID: " LS_LOAN-ID                               00443004
                                                                        00444003
           EXEC SQL                                                     00474000
                DELETE FROM KALA12.PAYPLAN                              00475006
                WHERE LOAN_ID = :LS_LOAN-ID                             00476002
           END-EXEC                                                     00477000
                                                                        00477106
           IF SQLCODE = 0                                               00477206
              DISPLAY "SUCCESSFULLY DELETED."                           00477306
              DISPLAY "SQL CODE IS: " SQLCODE                           00477406
           ELSE                                                         00477506
              DISPLAY "ERROR OCCURED DURING DELETION."                  00477606
              DISPLAY "SQL CODE IS: " SQLCODE                           00477706
              DISPLAY "SQLSTATE: " SQLSTATE                             00477806
           END-IF                                                       00477906
                                                                        00478006
           GOBACK.                                                      00478106
                                                                        00479000
      * CHECKING EXECUTION OF SQL STATEMENT.                            00730002
                                                                        00731006
      *    IF SQLCODE = 0                                               00740006
      *       DISPLAY "SUCCESSFULLY DELETED."                           00750006
      *       DISPLAY "SQL CODE IS: " SQLCODE                           00760006
      *    ELSE                                                         00770006
      *       DISPLAY "ERROR OCCURED DURING DELETION."                  00780006
      *       DISPLAY "SQL CODE IS: " SQLCODE                           00790006
      *       DISPLAY "SQLSTATE: " SQLSTATE                             00790106
      *       PERFORM ROLLBACK-EXIT                                     00791006
      *    END-IF                                                       00800006
      *                                                                 00810006
      *    PERFORM CURRENT-TIMESTAMP                                    00820006
      *                                                                 00821006
      *    GOBACK.                                                      00822006
      *                                                                 00830006
      *                                                                 00840006
      *ROLLBACK-EXIT.                                                   00851006
      * ROLLBACK AND RETURN TO MAIN PGM.                                00852000
      *                                                                 00853006
      *    EXEC SQL                                                     00854006
      *         ROLLBACK                                                00855006
      *    END-EXEC                                                     00856006
      *                                                                 00857006
      *    IF SQLCODE = 0                                               00859006
      *       DISPLAY "SUCCESSFULL ROLLBACK."                           00859106
      *       DISPLAY "SQL CODE IS: " SQLCODE                           00859206
      *    ELSE                                                         00859306
      *       DISPLAY "ERROR OCCURED DURING ROLLBACK."                  00859406
      *       DISPLAY "SQL CODE IS: " SQLCODE                           00859506
      *    END-IF                                                       00859706
      *                                                                 00859806
      *    DISPLAY "RETURNING TO MAIN PROGRAM."                         00859906
      *                                                                 00860006
      *    EXIT PROGRAM.                                                00860106
      *                                                                 00860306
      *                                                                 00860406
      *CURRENT-TIMESTAMP.                                               00861006
      * FINDING AND DISPLAYING CURRENT TIMESTAMP.                       00870000
      *                                                                 00880006
      *    EXEC SQL                                                     00890006
      *        SELECT CURRENT TIMESTAMP                                 00900006
      *        INTO                                                     00910006
      *               :DLT-TIMESTAMP                                    00920006
      *        FROM SYSIBM.SYSDUMMY1                                    00930006
      *    END-EXEC                                                     00940006
      *                                                                 00950006
      *    IF SQLCODE = 0                                               00960006
      *       DISPLAY "CURRENT TIME IS: " DLT-TIMESTAMP                 00980006
      *       DISPLAY " "                                               00981006
      *    ELSE                                                         00990006
      *       DISPLAY "ERROR RETRIVING TIMESTAMP. " SQLCODE             01000006
      *       DISPLAY " "                                               01001006
      *    END-IF.                                                      01020006
      *                                                                 01050006
