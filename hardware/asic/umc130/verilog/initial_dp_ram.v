`ifdef SRAM_INIT
   initial begin
      // wait for 5 clock cycles
      repeat (5) @(posedge CKA);

      $readmemh("tester_firmware_0.hex", Memory_byte0, 0, (Words-1));
      $readmemh("tester_firmware_1.hex", Memory_byte1, 0, (Words-1));
      $readmemh("tester_firmware_2.hex", Memory_byte2, 0, (Words-1));
      $readmemh("tester_firmware_3.hex", Memory_byte3, 0, (Words-1));
   end
`endif
