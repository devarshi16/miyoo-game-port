#ifndef MIYOO_CORE_H
#define MIYOO_CORE_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

#define MIYOO_API __attribute__((visibility("default")))

/* Gamepad button bitmask */
#define BTN_UP      (1 << 0)
#define BTN_DOWN    (1 << 1)
#define BTN_LEFT    (1 << 2)
#define BTN_RIGHT   (1 << 3)
#define BTN_A       (1 << 4)
#define BTN_B       (1 << 5)
#define BTN_X       (1 << 6)
#define BTN_Y       (1 << 7)
#define BTN_L1      (1 << 8)
#define BTN_R1      (1 << 9)
#define BTN_L2      (1 << 10)
#define BTN_R2      (1 << 11)
#define BTN_START   (1 << 12)
#define BTN_SELECT  (1 << 13)
#define BTN_MENU    (1 << 14)
#define BTN_POWER   (1 << 15)

/* Core lifecycle */
MIYOO_API bool     miyoo_init(int render_w, int render_h, int scale_factor);
MIYOO_API void     miyoo_shutdown(void);
MIYOO_API void     miyoo_clear(uint32_t argb_color);
MIYOO_API void     miyoo_flip(void);
MIYOO_API uint32_t miyoo_get_input(void);

/* Texture management */
MIYOO_API int      miyoo_tex_create_rgba(int w, int h, const uint32_t *pixels);
MIYOO_API int      miyoo_tex_create_indexed8(int w, int h, const uint8_t *indices, const uint32_t *palette_rgba);
MIYOO_API void     miyoo_tex_destroy(int tex_id);

/* Drawing primitives */
MIYOO_API void     miyoo_draw_sprite(int tex_id, int dx, int dy, int sx, int sy, int sw, int sh,
                                     uint32_t tint_rgba, bool flip_x, bool flip_y);

#ifdef __cplusplus
}
#endif

#endif /* MIYOO_CORE_H */
