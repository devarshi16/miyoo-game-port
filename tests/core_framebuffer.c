#include <assert.h>
#include <fcntl.h>
#include <linux/fb.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
static int depth=32, maps, final_pan;
static size_t mapped_size;
static uint8_t *mapped;
static int fake_open(const char *name,int flags,...){(void)flags;return strcmp(name,"/dev/fb0")==0?42:-1;}
static int fake_close(int fd){(void)fd;return 0;}
static int fake_ioctl(int fd,unsigned long req,...){(void)fd;va_list a;va_start(a,req);void *p=va_arg(a,void*);va_end(a);
 if(req==FBIOGET_VSCREENINFO){struct fb_var_screeninfo *v=p;memset(v,0,sizeof(*v));v->xres=640;v->yres=480;v->yres_virtual=1440;v->bits_per_pixel=depth;v->yoffset=960;v->red.offset=16;v->green.offset=8;v->blue.offset=0;v->transp.offset=24;v->red.length=v->green.length=v->blue.length=v->transp.length=8;}
 else if(req==FBIOGET_FSCREENINFO){struct fb_fix_screeninfo *f=p;memset(f,0,sizeof(*f));f->line_length=640*4+16;f->smem_len=f->line_length*1440;}
 else if(req==FBIOPAN_DISPLAY)final_pan=((struct fb_var_screeninfo*)p)->yoffset;
 return 0;}
static void *fake_mmap(void *a,size_t n,int p,int f,int fd,off_t o){(void)a;(void)p;(void)f;(void)fd;(void)o;maps++;mapped_size=n;mapped=malloc(n+64);memset(mapped,0xA5,n+64);return mapped;}
static int fake_munmap(void *a,size_t n){for(size_t i=n;i<n+64;i++)assert(((uint8_t*)a)[i]==0xA5);free(a);mapped=NULL;return 0;}
#define open fake_open
#define close fake_close
#define ioctl fake_ioctl
#define mmap fake_mmap
#define munmap fake_munmap
#include "../templates/native_core/miyoo_core.c"
int main(void){
 assert(miyoo_init(320,240,2));miyoo_clear(0xff000000);uint32_t translucent=0xfe0000ff;int tex=miyoo_tex_create_rgba(1,1,&translucent);
 miyoo_draw_sprite(tex,0,0,0,0,1,1,0xffffffff,false,false);assert(g_render_buffer[0]==0xff0000fe);
 g_render_buffer[239*320+319]=0xff0000ff;miyoo_flip();
 assert(final_pan==0);assert(*(uint32_t*)mapped==0xffff0000);assert(mapped[640*4]==0xA5);
 miyoo_shutdown();assert(final_pan==960);miyoo_shutdown();depth=16;int before=maps;assert(!miyoo_init(320,240,2));assert(maps==before);
 assert(!miyoo_init(640,480,1));return 0;
}
