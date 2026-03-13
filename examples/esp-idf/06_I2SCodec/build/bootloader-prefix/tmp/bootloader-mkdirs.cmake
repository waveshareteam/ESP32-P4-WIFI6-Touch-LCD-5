# Distributed under the OSI-approved BSD 3-Clause License.  See accompanying
# file Copyright.txt or https://cmake.org/licensing for details.

cmake_minimum_required(VERSION 3.5)

file(MAKE_DIRECTORY
  "/home/yeechan/esp-idf-v5.5.3/components/bootloader/subproject"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/tmp"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/src/bootloader-stamp"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/src"
  "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/src/bootloader-stamp"
)

set(configSubDirs )
foreach(subDir IN LISTS configSubDirs)
    file(MAKE_DIRECTORY "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/src/bootloader-stamp/${subDir}")
endforeach()
if(cfgdir)
  file(MAKE_DIRECTORY "/home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/06_I2SCodec/build/bootloader-prefix/src/bootloader-stamp${cfgdir}") # cfgdir has leading slash
endif()
