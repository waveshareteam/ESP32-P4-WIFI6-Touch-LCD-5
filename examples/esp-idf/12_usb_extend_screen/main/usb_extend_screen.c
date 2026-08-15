/*
 * SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Apache-2.0
 */

#include <stdio.h>
#include "bsp/esp-bsp.h"
#include "bsp/touch.h"
#include "esp_lcd_touch.h"
#include "app_usb.h"
#include "usb_descriptors.h"
#include "esp_log.h"
#if CONFIG_HID_TOUCH_ENABLE
#include "app_touch.h"
#endif
#include "app_lcd.h"

static const char *TAG = "usb_extend_screen";

_Static_assert(USB_EXTEND_SCREEN_H_RES == BSP_LCD_H_RES, "USB display width must match the BSP");
_Static_assert(USB_EXTEND_SCREEN_V_RES == BSP_LCD_V_RES, "USB display height must match the BSP");

void app_main(void)
{
    ESP_LOGI(TAG, "USB extend screen example");
    app_usb_init();
    app_lcd_init();
#if CONFIG_HID_TOUCH_ENABLE
    app_touch_init();
#endif
    app_uac_init();
}
