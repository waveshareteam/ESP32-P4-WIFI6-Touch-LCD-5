/*
* SPDX-FileCopyrightText: 2024 Espressif Systems (Shanghai) CO LTD
*
* SPDX-License-Identifier: ESPRESSIF MIT
*/

#include <string.h>
#include "esp_ipa.h"

typedef struct esp_video_ipa_index {
    const char *name;
    const esp_ipa_config_t *ipa_config;
} esp_video_ipa_index_t;

static const esp_ipa_adn_bf_t s_ipa_adn_bf_OV5647_config[] = {
    {
        .gain = 1000,
        .bf = {
            .level = 5,
            .matrix = {
                {1, 2, 1},
                {2, 4, 2},
                {1, 2, 1}
            }
        }
    },
};

static const esp_ipa_adn_config_t s_ipa_adn_OV5647_config = {
    .bf_table = s_ipa_adn_bf_OV5647_config,
    .bf_table_size = ARRAY_SIZE(s_ipa_adn_bf_OV5647_config),
};

static const esp_ipa_aen_gamma_unit_t s_esp_ipa_aen_gamma_OV5647_table[] = {
    {
        .luma = 71.1000,
        .gamma_param = 0.7200,
    },
};

static const esp_ipa_aen_gamma_config_t s_ipa_aen_gamma_OV5647_config = {
    .use_gamma_param = true,
    .luma_env = "ae.luma.avg",
    .luma_min_step = 16.0000,
    .gamma_table = s_esp_ipa_aen_gamma_OV5647_table,
    .gamma_table_size = 1,
};

static const esp_ipa_aen_sharpen_t s_ipa_aen_sharpen_OV5647_config[] = {
    {
        .gain = 1000,
        .sharpen = {
            .h_thresh = 56,
            .l_thresh = 10,
            .h_coeff = 0.4250,
            .m_coeff = 0.6250,
            .matrix = {
                {1, 2, 1},
                {2, 2, 2},
                {1, 2, 1}
            }
        }
    },
};

static const esp_ipa_aen_con_t s_ipa_aen_con_OV5647_config[] = {
    {
        .gain = 1000,
        .contrast = 134
    },
};

static const esp_ipa_aen_config_t s_ipa_aen_OV5647_config = {
    .gamma = &s_ipa_aen_gamma_OV5647_config,
    .sharpen_table = s_ipa_aen_sharpen_OV5647_config,
    .sharpen_table_size = ARRAY_SIZE(s_ipa_aen_sharpen_OV5647_config),
    .con_table = s_ipa_aen_con_OV5647_config,
    .con_table_size = ARRAY_SIZE(s_ipa_aen_con_OV5647_config),
};

static const esp_ipa_ian_luma_ae_config_t s_esp_ipa_ian_luma_ae_OV5647_config = {                 
    .weight = {
        1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,1,
    },
};

static const esp_ipa_ian_luma_config_t s_esp_ipa_ian_luma_OV5647_config = {
    .ae = &s_esp_ipa_ian_luma_ae_OV5647_config,
};

static const esp_ipa_ian_config_t s_ipa_ian_OV5647_config = {
    .luma = &s_esp_ipa_ian_luma_OV5647_config,
};

static const esp_ipa_acc_sat_t s_ipa_acc_sat_OV5647_config[] = {
    {
        .color_temp = 0,
        .saturation = 128
    },
};

static const esp_ipa_acc_ccm_unit_t s_esp_ipa_acc_ccm_OV5647_table[] = {
    {
        .color_temp = 0,
        .ccm = {
            .matrix = {
                { 2.0000, -0.5459, -0.4541 },
                { -0.4751, 1.7696, -0.2945 },
                { -0.2002, -0.7998, 2.0000 }
            }
        }
    },
};

static const esp_ipa_acc_ccm_config_t s_esp_ipa_acc_ccm_OV5647_config = {
    .luma_env = "ae.luma.avg",
    .luma_low_threshold = 28.0000,
    .luma_low_ccm = {
        .matrix = {
            { 1.0000, 0.0000, 0.0000 },
            { 0.0000, 1.0000, 0.0000 },
            { 0.0000, 0.0000, 1.0000 }
        }
    }
    ,
    .ccm_table = s_esp_ipa_acc_ccm_OV5647_table,
    .ccm_table_size = 1,
};

static const esp_ipa_acc_config_t s_ipa_acc_OV5647_config = {
    .sat_table = s_ipa_acc_sat_OV5647_config,
    .sat_table_size = ARRAY_SIZE(s_ipa_acc_sat_OV5647_config),
    .ccm = &s_esp_ipa_acc_ccm_OV5647_config,
};

static const char *s_ipa_OV5647_names[] = {
    "esp_ipa_adn",
    "esp_ipa_aen",
    "esp_ipa_ian",
    "esp_ipa_acc",
};

static const esp_ipa_config_t s_ipa_OV5647_config = {
    .names = s_ipa_OV5647_names,
    .nums = ARRAY_SIZE(s_ipa_OV5647_names),
    .version = 1,
    .adn = &s_ipa_adn_OV5647_config,
    .aen = &s_ipa_aen_OV5647_config,
    .ian = &s_ipa_ian_OV5647_config,
    .acc = &s_ipa_acc_OV5647_config,
};

static const esp_video_ipa_index_t s_video_ipa_configs[] = {
    {
        .name = "OV5647",
        .ipa_config = &s_ipa_OV5647_config
    },
};

const esp_ipa_config_t *esp_ipa_pipeline_get_config(const char *name)
{
    for (int i = 0; i < ARRAY_SIZE(s_video_ipa_configs); i++) {
        if (!strcmp(name, s_video_ipa_configs[i].name)) {
            return s_video_ipa_configs[i].ipa_config;
        }
    }
    return NULL;
}

/* Json file: /home/yeechan/sourcecode/esp32-p4/external/esp32-p4-wifi6-touch-lcd-5/examples/esp-idf/09_video_lcd_display/managed_components/espressif__esp_cam_sensor/sensors/ov5647/cfg/ov5647_default.json */

