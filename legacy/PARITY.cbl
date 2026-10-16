       IDENTIFICATION DIVISION.
       PROGRAM-ID. PARITY.
      * Test driver, not part of the legacy system. Reads a count,
      * then that many 33-character order lines from standard input,
      * calls ORDPRICE for each, and prints the total and the status.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-COUNT             PIC 9(6).
       01  WS-I                 PIC 9(6).
       01  WS-ORDER-LINE        PIC X(33).
       01  WS-RESULT.
           05  WS-TOTAL         PIC 9(7)V99.
           05  WS-STATUS        PIC X.
       PROCEDURE DIVISION.
           ACCEPT WS-COUNT
           PERFORM VARYING WS-I FROM 1 BY 1 UNTIL WS-I > WS-COUNT
               ACCEPT WS-ORDER-LINE
               MOVE ZERO TO WS-TOTAL
               MOVE SPACE TO WS-STATUS
               CALL 'ORDPRICE' USING WS-ORDER-LINE WS-RESULT
               DISPLAY WS-TOTAL WS-STATUS
           END-PERFORM
           STOP RUN.
