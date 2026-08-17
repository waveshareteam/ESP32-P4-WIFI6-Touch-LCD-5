idf_component_register(SRCS "sd_test_io.c"
                       INCLUDE_DIRS "."
                       REQUIRES fatfs esp_adc esp_driver_gpio
                       WHOLE_ARCHIVE)
