       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORDPRICE.
      * Prices one order line for the order entry system.
      * Called by ORDENTRY once per line. Written 1994.
      * Volume break added 2003, pricing memo PM-114.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-DISC-PCT          PIC V999      VALUE ZERO.
       01  WS-VOL-PCT           PIC V999      VALUE ZERO.
       01  WS-TAX-PCT           PIC V9999     VALUE ZERO.
       01  WS-GROSS             PIC 9(7)V99   VALUE ZERO.
       01  WS-NET               PIC 9(7)V99   VALUE ZERO.
       01  WS-TAX               PIC 9(7)V99   VALUE ZERO.
       01  WS-FEE               PIC 9(3)V99   VALUE ZERO.
       LINKAGE SECTION.
       01  LK-ORDER-LINE.
           05  LK-CUST-TYPE     PIC X.
               88  CUST-RETAIL      VALUE 'R'.
               88  CUST-WHOLESALE   VALUE 'W'.
               88  CUST-GOVT        VALUE 'G'.
           05  LK-QTY           PIC 9(5).
           05  LK-UNIT-PRICE    PIC 9(5)V99.
           05  LK-STATE         PIC XX.
           05  LK-CREDIT-LIMIT  PIC 9(7)V99.
           05  LK-OPEN-BALANCE  PIC 9(7)V99.
       01  LK-RESULT.
           05  LK-TOTAL         PIC 9(7)V99.
           05  LK-STATUS        PIC X.
       PROCEDURE DIVISION USING LK-ORDER-LINE LK-RESULT.
       0000-MAIN.
           PERFORM 1000-CUSTOMER-DISCOUNT
           PERFORM 2000-VOLUME-DISCOUNT
           PERFORM 3000-SMALL-ORDER-FEE
           PERFORM 4000-SALES-TAX
           PERFORM 5000-CREDIT-CHECK
           GOBACK.
       1000-CUSTOMER-DISCOUNT.
           EVALUATE TRUE
               WHEN CUST-WHOLESALE  MOVE .080 TO WS-DISC-PCT
               WHEN CUST-GOVT       MOVE .050 TO WS-DISC-PCT
               WHEN OTHER           MOVE ZERO TO WS-DISC-PCT
           END-EVALUATE
           COMPUTE WS-GROSS ROUNDED = LK-QTY * LK-UNIT-PRICE
           COMPUTE WS-NET ROUNDED = WS-GROSS * (1 - WS-DISC-PCT).
       2000-VOLUME-DISCOUNT.
           IF LK-QTY >= 100
               MOVE .030 TO WS-VOL-PCT
               COMPUTE WS-NET ROUNDED = WS-NET * (1 - WS-VOL-PCT)
           END-IF.
       3000-SMALL-ORDER-FEE.
           MOVE ZERO TO WS-FEE
           IF WS-NET < 25.00 AND NOT CUST-GOVT
               MOVE 4.95 TO WS-FEE
           END-IF
           ADD WS-FEE TO WS-NET.
       4000-SALES-TAX.
           IF CUST-GOVT
               MOVE ZERO TO WS-TAX-PCT
           ELSE
               EVALUATE LK-STATE
                   WHEN 'TX'   MOVE .0625 TO WS-TAX-PCT
                   WHEN 'CA'   MOVE .0725 TO WS-TAX-PCT
                   WHEN OTHER  MOVE .0500 TO WS-TAX-PCT
               END-EVALUATE
           END-IF
           COMPUTE WS-TAX ROUNDED = WS-NET * WS-TAX-PCT
           COMPUTE LK-TOTAL = WS-NET + WS-TAX.
       5000-CREDIT-CHECK.
      * Hold the order if it would push the customer over limit.
           IF LK-OPEN-BALANCE + LK-TOTAL > LK-CREDIT-LIMIT
               MOVE 'H' TO LK-STATUS
           ELSE
               MOVE 'A' TO LK-STATUS
           END-IF.
