//KALA12D JOB MSGLEVEL=(1,1),NOTIFY=&SYSUID                             00010000
//PLIB    JCLLIB ORDER=(MATE1.PROCLIB)                                  00011000
//*                                                                     00020000
//*  COBOL + DB2 PRECOMPILE AND LINKEDIT                                00030000
//*                                                                     00040000
//DBPREC  EXEC DB2COBCL,                                                00071000
//             COPYLIB=KALA12.COPYLIB,         <= COPYBOOK LIBRARY      00072000
//             DCLGLIB=KALA12.DCLGEN.COBOL,    <= DCLGEN LIBRARY        00072100
//             DBRMLIB=KALA12.DBRMLIB,         <= DBRM LIBRARY          00072200
//             LOADLIB=KALA12.LOADLIB,         <= LOAD LIBRARY          00072300
//             SRCLIB=KALA12.COBOL.SRCLIB,     <= SOURCE LIBRARY        00073000
//             MEMBER=LNDWISE4     <= SOURCE MEMBER                     00074051
