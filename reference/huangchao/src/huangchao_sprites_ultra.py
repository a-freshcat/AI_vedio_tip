"""《黄巢五幕》V3 · 128×128 原生高精度像素人物绘制引擎

不是将旧图放大：所有轮廓、脸部、纹样、服装、武具均在 128×128 原生网格绘制。
五幕 × 四个独立动作 = 20 帧；透明 RGBA / 像素图集 / GIF / 审图板。
保持调用接口 get_huangchao_sprite(stage_key, frame=0, scale=4)。
原生尺寸增至 128×128，实际项目内 scale=1 即可。

注意：五幕故事造型为游戏美术演绎，不表示对黄巢史实相貌或具体冠服的考古复原。
依赖：Pillow   运行：python huangchao_sprites_ultra.py
"""
from __future__ import annotations
import math
from pathlib import Path
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont, ImageFilter

SIZE = 128
OUT = Path(__file__).resolve().parent
RGBA = Tuple[int,int,int,int]
# 多档明暗为塑造体积服务：每种材质拥有基色、受光色与背光色。
RGB = {
 'none': (0,0,0,0), 'ink':(22,22,31,255), 'edge':(42,35,39,255),
 'hair0':(27,28,35,255),'hair1':(48,44,50,255),'hair2':(84,76,74,255),'hair3':(119,99,89,255),
 'skin0':(99,63,64,255),'skin1':(165,104,81,255),'skin2':(213,151,110,255),
 'skin3':(239,185,135,255),'skin4':(255,215,164,255),'skin5':(255,234,189,255),
 'eye':(254,243,213,255), 'ash':(137,113,103,255),
 'teal0':(19,56,70,255),'teal1':(30,79,91,255),'teal2':(41,108,121,255),
 'teal3':(63,136,145,255),'teal4':(104,171,170,255),'teal5':(153,195,181,255),
 'ivory0':(151,121,91,255),'ivory1':(205,175,127,255),'ivory2':(241,218,169,255),'ivory3':(255,243,201,255),
 'red0':(69,27,42,255),'red1':(111,34,50,255),'red2':(161,44,58,255),
 'red3':(205,66,67,255),'red4':(239,112,95,255),
 'brown0':(48,42,46,255),'brown1':(69,49,50,255),'brown2':(98,67,57,255),
 'brown3':(135,93,66,255),'brown4':(177,128,83,255),
 'iron0':(29,42,61,255),'iron1':(45,66,84,255),'iron2':(69,94,110,255),
 'iron3':(104,132,144,255),'iron4':(156,180,181,255),'iron5':(207,219,207,255),
 'steel0':(71,99,117,255),'steel1':(131,160,173,255),'steel2':(189,213,211,255),
 'steel3':(244,242,217,255),
 'gold0':(104,65,42,255),'gold1':(152,98,41,255),'gold2':(196,138,49,255),
 'gold3':(230,173,62,255),'gold4':(255,210,94,255),'gold5':(255,237,156,255),
 'dust0':(76,70,74,255),'dust1':(112,104,99,255),'dust2':(159,139,111,255),
 'blood':(130,24,43,255),'bloodlight':(184,41,48,255),
}
PALETTE: Dict[str,RGBA] = RGB

class PixelCanvas:
    """所有绘画直接落在 RGBA 原生像素网格；没有缩放、矢量抗锯齿或随机噪点。"""
    def __init__(self):
        self.im=Image.new('RGBA',(SIZE,SIZE),RGB['none'])
        self.d=ImageDraw.Draw(self.im)
    def poly(self,points,color): self.d.polygon([(round(x),round(y)) for x,y in points],fill=RGB[color])
    def rect(self,box,color): self.d.rectangle(tuple(map(round,box)),fill=RGB[color])
    def line(self,pts,color,w=1): self.d.line([(round(x),round(y)) for x,y in pts],fill=RGB[color],width=w,joint='curve')
    def dot(self,x,y,color): self.d.point((round(x),round(y)),fill=RGB[color])
    def ell(self,box,color): self.d.ellipse(tuple(map(round,box)),fill=RGB[color])
    def finish(self):
        # 仅沿最终精灵轮廓做 1px 墨线，不破坏布纹、瞳孔和甲片内部细节
        mask=self.im.getchannel('A'); spread=mask.filter(ImageFilter.MaxFilter(3))
        outline=Image.new('RGBA',(SIZE,SIZE),RGB['ink']); outline.putalpha(spread)
        outline.alpha_composite(self.im)
        return outline


def _face(p, cx, y, mode, feeling='stern', turn=False):
    """五幕共享同一人的窄眉眼、高鼻梁、硬朗八字胡和分叉长须。"""
    # 发髻、两颊后方的鬓发与轮廓，避免头部是纯方块
    p.poly([(cx-15,y+7),(cx-14,y-2),(cx-10,y-6),(cx-3,y-9),(cx+9,y-7),
            (cx+15,y-2),(cx+16,y+10),(cx+12,y+26),(cx-13,y+28)],'hair0')
    p.poly([(cx-13,y+0),(cx-8,y-7),(cx+6,y-7),(cx+13,y-1),(cx+11,y+8),
            (cx+7,y+5),(cx-10,y+9)],'hair1')
    p.line([(cx-10,y-2),(cx-5,y-6),(cx+3,y-6)],'hair2',2)
    # 面颊与下颌以多色块模拟斜向光照
    p.poly([(cx-10,y+7),(cx+9,y+5),(cx+13,y+11),(cx+12,y+22),
            (cx+6,y+29),(cx-3,y+31),(cx-11,y+25),(cx-13,y+17)],'skin1')
    p.poly([(cx-10,y+8),(cx+7,y+7),(cx+10,y+12),(cx+8,y+23),
            (cx+3,y+27),(cx-7,y+24),(cx-11,y+17)],'skin3')
    p.poly([(cx-9,y+9),(cx+2,y+7),(cx+7,y+11),(cx+5,y+16),(cx-7,y+18)],'skin4')
    p.line([(cx-8,y+20),(cx-6,y+24)],'skin2',2)
    p.rect((cx-13,y+15,cx-11,y+21),'skin2')
    p.rect((cx+10,y+15,cx+12,y+21),'skin1')
    p.dot(cx-12,y+17,'skin4')
    if not turn:
        eyebrow_y= y+12 if feeling!='angry' else y+10
        p.line([(cx-9,eyebrow_y),(cx-3,eyebrow_y+1)],'hair0',3)
        p.line([(cx+2,eyebrow_y+1),(cx+9,eyebrow_y)],'hair0',3)
        p.line([(cx-7,y+16),(cx-3,y+16)],'hair0',2)
        p.line([(cx+4,y+16),(cx+8,y+16)],'hair0',2)
        p.dot(cx-4,y+16,'eye');p.dot(cx+7,y+16,'eye')
        p.line([(cx+1,y+17),(cx+2,y+21),(cx+5,y+22)],'skin1',2)
        p.dot(cx+2,y+18,'skin5')
        p.line([(cx-7,y+22),(cx-5,y+23)],'skin2')
    else:
        # 侧回望：半张脸，眼神在一侧，另一侧是鬓发
        p.line([(cx+4,y+12),(cx+10,y+13)],'hair0',3)
        p.rect((cx+7,y+16,cx+10,y+17),'hair0')
        p.dot(cx+9,y+16,'eye')
        p.poly([(cx-12,y+5),(cx-4,y+5),(cx-5,y+23),(cx-12,y+21)],'hair1')
    # 络腮胡和胡须分叉，露出口部肌理
    p.poly([(cx-10,y+22),(cx-6,y+23),(cx-3,y+24),(cx+1,y+23),
            (cx+6,y+24),(cx+11,y+22),(cx+10,y+27),(cx+5,y+28),
            (cx+4,y+33),(cx-5,y+34),(cx-9,y+28)],'hair0')
    p.line([(cx-10,y+23),(cx-6,y+25),(cx-2,y+24)],'hair2',2)
    p.line([(cx+2,y+24),(cx+7,y+25),(cx+10,y+23)],'hair2',2)
    p.rect((cx-2,y+26,cx+2,y+27),'skin1')
    p.poly([(cx-8,y+28),(cx-5,y+31),(cx-5,y+38),(cx-1,y+43),
            (cx+2,y+40),(cx+4,y+34),(cx+6,y+30),(cx+3,y+32),
            (cx+1,y+35),(cx-2,y+32)],'hair0')
    p.line([(cx-5,y+33),(cx-3,y+39)],'hair2')
    p.line([(cx+3,y+32),(cx+2,y+38)],'hair1',2)
    if mode=='wounded':
        p.line([(cx+11,y+14),(cx+8,y+18),(cx+10,y+21)],'blood',2)
        p.line([(cx-9,y+21),(cx-6,y+23)],'bloodlight')
        p.line([(cx-5,y+19),(cx-2,y+20)],'ash')
    # 头饰绘制在脸上方，但不盖过眉眼
    if mode=='scholar':
        p.poly([(cx-15,y+7),(cx-15,y-3),(cx-11,y-8),(cx-5,y-10),
                (cx+8,y-9),(cx+14,y-5),(cx+15,y+6)],'hair0')
        p.poly([(cx-11,y-7),(cx+7,y-7),(cx+10,y-3),(cx-13,y-2)],'hair2')
        p.rect((cx-16,y+3,cx+16,y+7),'hair0')
        p.line([(cx-14,y+3),(cx-21,y-2),(cx-28,y-3)],'hair0',4)
        p.line([(cx+14,y+3),(cx+21,y-1),(cx+28,y-2)],'hair0',4)
        p.line([(cx-23,y-3),(cx-27,y-3)],'hair2',2)
        p.line([(cx+19,y-2),(cx+25,y-3)],'hair2',2)
        p.rect((cx-3,y-8,cx+4,y-7),'hair3')
    elif mode=='bandana':
        p.poly([(cx-14,y+1),(cx-12,y-5),(cx+12,y-5),(cx+15,y+1),
                (cx+14,y+8),(cx-14,y+8)],'red1')
        p.poly([(cx-14,y+0),(cx+14,y),(cx+13,y+5),(cx-14,y+5)],'red3')
        p.line([(cx-12,y+1),(cx+11,y+1)],'red4',2)
        p.line([(cx-12,y+6),(cx+13,y+6)],'red0',2)
        p.poly([(cx-13,y+3),(cx-22,y+4),(cx-31,y+10),(cx-25,y+13),
                (cx-17,y+10)],'red2')
        p.line([(cx-24,y+9),(cx-29,y+10)],'red4',2)
    elif mode=='helmet':
        p.poly([(cx-16,y+6),(cx-14,y-8),(cx-8,y-14),(cx+5,y-16),
                (cx+13,y-10),(cx+16,y+6)],'iron0')
        p.poly([(cx-12,y+2),(cx-10,y-9),(cx-5,y-12),(cx+5,y-12),
                (cx+11,y-6),(cx+12,y+2)],'iron2')
        p.line([(cx-10,y-6),(cx-6,y-11),(cx+2,y-11)],'iron4',3)
        p.line([(cx-15,y+5),(cx+15,y+5)],'gold2',3)
        p.line([(cx-12,y+7),(cx-10,y+23)],'iron1',5)
        p.line([(cx+13,y+7),(cx+11,y+22)],'iron1',5)
        p.rect((cx-14,y+18,cx-11,y+21),'gold3')
        p.rect((cx+11,y+18,cx+14,y+21),'gold3')
        p.poly([(cx-3,y-14),(cx-2,y-22),(cx+1,y-26),(cx+4,y-14)],'red2')
        p.line([(cx,y-23),(cx+2,y-15)],'red4',2)
        p.poly([(cx-9,y+2),(cx-2,y-3),(cx+7,y-2),(cx+10,y+3)],'iron3')
        p.line([(cx-5,y-1),(cx+5,y-1)],'iron5')
    elif mode=='crown':
        p.poly([(cx-10,y-8),(cx-8,y-15),(cx+9,y-15),(cx+11,y-7),
                (cx+11,y+4),(cx-10,y+4)],'gold1')
        p.rect((cx-8,y-13,cx+8,y-10),'gold4')
        p.rect((cx-8,y-10,cx+8,y-8),'red1')
        p.rect((cx-18,y-19,cx+18,y-15),'gold1')
        p.rect((cx-17,y-21,cx+17,y-19),'gold4')
        p.line([(cx-12,y-19),(cx+12,y-19)],'gold5')
        p.rect((cx-4,y-16,cx+3,y-13),'red3')
        for x,dy in ((cx-16,1),(cx-12,5),(cx+12,5),(cx+16,1)):
            p.line([(x,y-16),(x,y+dy+4)],'gold3')
            p.dot(x,y+dy+4,'gold5')
            p.dot(x,y+dy+2,'red3')
    elif mode=='wounded':
        p.poly([(cx-14,y+4),(cx-12,y-9),(cx-6,y-13),(cx+7,y-11),
                (cx+15,y+1),(cx+14,y+7),(cx-10,y+8)],'hair0')
        p.line([(cx-11,y-3),(cx-17,y+9),(cx-16,y+31)],'hair1',4)
        p.line([(cx+10,y-6),(cx+18,y+9),(cx+17,y+28)],'hair0',4)
        p.line([(cx-7,y-8),(cx+3,y-10)],'hair3',2)


def _boots(p,cx,step=0,metal=False):
    l=cx-11-step; r=cx+9+step
    base='iron1' if metal else 'brown1'; shade='iron0' if metal else 'brown0'
    light='iron3' if metal else 'brown3'
    p.poly([(l-5,87),(l+5,87),(l+4,114),(l-7,114)],base)
    p.poly([(r-5,87),(r+6,87),(r+8,114),(r-4,114)],base)
    p.line([(l-3,91),(l-2,107)],light,2)
    p.line([(r+2,91),(r+4,106)],light,2)
    for y in (95,102,109):
        p.line([(l-4,y),(l+4,y+1)],shade,2)
        p.line([(r-3,y+1),(r+6,y)],shade,2)
    p.poly([(l-7,112),(l+5,112),(l+5,119),(l-11,119),(l-12,116)],shade)
    p.poly([(r-4,112),(r+7,112),(r+12,117),(r+10,120),(r-4,120)],shade)
    p.line([(l-9,118),(l+5,118)],light)
    p.line([(r-2,119),(r+9,119)],light)
    if metal:
        p.line([(l-4,94),(l+3,94)],'steel2')
        p.line([(r-3,94),(r+6,94)],'steel2')
        p.dot(l,102,'gold3');p.dot(r+1,102,'gold3')


def _arm(p, a, b, c, style, extra=0):
    """真正弯折的袖管：双层布、斜向折光、袖口及手套。"""
    if style=='scholar': sh,base,lit,cuff='teal0','teal2','teal4','ivory2'; width=11
    elif style=='rebel': sh,base,lit,cuff='brown0','brown2','brown4','red2';width=10
    elif style=='general':sh,base,lit,cuff='iron0','iron2','iron4','gold2';width=10
    elif style=='emperor':sh,base,lit,cuff='gold0','gold3','gold5','red2';width=13
    else: sh,base,lit,cuff='iron0','gold1','gold3','dust1';width=10
    p.line([a,b],sh,width+5);p.line([a,b],base,width+2)
    p.line([b,c],sh,width+4);p.line([b,c],base,width)
    # 织物受光为偏左断续亮带，不是整条中线
    p.line([(a[0]-2,a[1]-2),(b[0]-2,b[1]-2)],lit,3)
    p.line([(b[0]-2,b[1]-2),(c[0]-2,c[1]-2)],lit,2)
    p.line([(b[0]-3,b[1]+2),(b[0]+1,b[1]+4)],sh,2)
    p.line([(c[0]-4,c[1]-2),(c[0]+3,c[1]+1)],cuff,4)
    p.poly([(c[0]-3,c[1]-3),(c[0]+3,c[1]-2),(c[0]+4,c[1]+4),
            (c[0],c[1]+5),(c[0]-4,c[1]+3)],'skin2')
    p.line([(c[0]-2,c[1]-2),(c[0]+1,c[1]-2)],'skin4',2)


def _scroll(p,x,y,torn=False):
    if torn:
        p.poly([(x,y+2),(x+16,y-3),(x+23,y),(x+20,y+8),
                (x+16,y+6),(x+11,y+10),(x+6,y+6)],'ivory1')
        p.poly([(x+2,y+1),(x+16,y-2),(x+20,y+2),(x+15,y+6),(x+8,y+4)],'ivory3')
        p.line([(x+7,y+2),(x+14,y+1)],'brown3')
    else:
        p.poly([(x,y),(x+18,y-2),(x+21,y+20),(x+3,y+22)],'ivory0')
        p.poly([(x+2,y+2),(x+17,y),(x+19,y+18),(x+4,y+20)],'ivory2')
        p.line([(x+4,y+3),(x+17,y+2)],'ivory3',2)
        p.rect((x-1,y-2,x+4,y+3),'gold2')
        p.rect((x+17,y+17,x+22,y+22),'gold2')
        for dy in (7,10,13,16):
            p.line([(x+7,y+dy),(x+15,y+dy-1)],'ivory0')
        p.line([(x+8,y+6),(x+14,y+6)],'brown3')


def _sword(p, h, tip, gold=True):
    hx,hy=h; tx,ty=tip; dx=tx-hx;dy=ty-hy
    n=math.hypot(dx,dy) or 1;u=(dx/n,dy/n);v=(-u[1],u[0]);
    pt=lambda t,side: (hx+u[0]*t+v[0]*side,hy+u[1]*t+v[1]*side)
    # 剑柄、护手、双面剑脊和渐尖轮廓
    p.line([pt(-10,0),pt(1,0)],'brown0',6)
    p.line([pt(-8,-1),pt(-1,-1)],'brown4',2)
    p.ell((hx+u[0]*-12-3,hy+u[1]*-12-3,hx+u[0]*-12+3,hy+u[1]*-12+3),'gold3')
    p.line([pt(0,-9),pt(0,9)],'gold0',5)
    p.line([pt(-1,-8),pt(-1,8)],'gold4',2)
    p.poly([pt(1,-5),pt(n*.60,-4),pt(n*.88,-2),pt(n,0),
            pt(n*.88,2),pt(n*.60,4),pt(1,5)],'steel0')
    p.poly([pt(2,-3),pt(n*.6,-2),pt(n*.88,-1),pt(n,0),pt(2,1)],'steel2')
    p.line([pt(4,-2),pt(n*.8,-1)],'steel3',2)
    p.line([pt(3,2),pt(n*.8,1)],'steel1',2)
    p.dot(*pt(n-1,0),'steel3')


def _spear(p,base,tip):
    bx,by=base;tx,ty=tip
    dx=tx-bx;dy=ty-by;n=math.hypot(dx,dy) or 1
    u=(dx/n,dy/n);v=(-u[1],u[0])
    pt=lambda t,s:(bx+u[0]*t+v[0]*s,by+u[1]*t+v[1]*s)
    p.line([base,tip],'brown0',6)
    p.line([pt(0,-1),pt(n-3,-1)],'brown4',2)
    p.poly([pt(n-8,-5),pt(n+14,0),pt(n-8,5),pt(n-3,0)],'steel0')
    p.poly([pt(n-7,-3),pt(n+13,0),pt(n-3,0)],'steel2')
    p.line([pt(n-4,-2),pt(n+10,0)],'steel3')
    p.line([pt(n-8,0),pt(n-12,-12),pt(n-18,-18)],'red3',3)
    p.line([pt(n-8,0),pt(n-15,11),pt(n-20,16)],'red2',3)
    p.dot(*pt(n+13,0),'steel3')


def _flag(p,x,y,kind,phase=0,broken=False):
    if broken:
        p.line([(x,y+60),(x+5,y+85)],'brown0',6)
        p.line([(x+5,y+85),(x+16,y+95)],'brown3',3)
        p.poly([(x+5,y+60),(x+23,y+65),(x+37,y+75),
                (x+24,y+87),(x+10,y+79)],'gold0')
        p.poly([(x+7,y+62),(x+23,y+67),(x+31,y+76),(x+20,y+82)],'gold3')
        p.line([(x+13,y+67),(x+24,y+74),(x+18,y+78)],'red2',3)
        return
    p.line([(x,y),(x,y+109)],'brown0',6)
    p.line([(x-2,y+5),(x-2,y+107)],'brown4',2)
    p.rect((x-4,y-4,x+4,y+2),'gold1')
    p.rect((x-2,y-6,x+2,y-4),'gold5')
    wave=(phase%4-1)*3
    if kind=='rebel':
        p.poly([(x+3,y+5),(x+23,y+5+wave),(x+44,y+10+wave),
                (x+35,y+24+wave),(x+44,y+39+wave),(x+23,y+36+wave),
                (x+3,y+32)],'hair0')
        p.poly([(x+5,y+7),(x+23,y+8+wave),(x+39,y+12+wave),
                (x+32,y+24+wave),(x+39,y+35+wave),(x+7,y+30)],'red0')
        p.line([(x+6,y+8),(x+28,y+10+wave)],'red3',3)
        p.poly([(x+15,y+14),(x+23,y+12),(x+29,y+20),(x+24,y+29),
                (x+15,y+28),(x+11,y+20)],'red3')
        p.line([(x+17,y+17),(x+23,y+16),(x+25,y+20)],'red4',2)
        for i in range(4):p.line([(x+4+i*3,y+33),(x+2+i*3,y+38)],'red2')
    else:
        p.poly([(x+3,y+5),(x+23,y+6+wave),(x+43,y+13+wave),
                (x+35,y+25+wave),(x+43,y+44+wave),(x+24,y+39+wave),
                (x+3,y+37)],'gold0')
        p.poly([(x+5,y+7),(x+24,y+9+wave),(x+37,y+15+wave),
                (x+31,y+24+wave),(x+37,y+39+wave),(x+7,y+34)],'gold3')
        p.line([(x+6,y+8),(x+25,y+10+wave)],'gold5',2)
        # 旗心赤龙简化轮廓而非模糊文字
        p.line([(x+13,y+17),(x+24,y+15+wave),(x+29,y+22+wave),
                (x+18,y+27),(x+27,y+32)],'red2',4)
        p.line([(x+15,y+17),(x+22,y+17)],'red4',2)
        p.line([(x+11,y+32),(x+35,y+36+wave)],'gold5')
        for i in range(5):p.line([(x+5+i*4,y+37),(x+4+i*4,y+41)],'gold2')


def _coat_scholar(p,cx,action=0):
    _boots(p,cx,2 if action==2 else 0,False)
    # 分层广袖长袍，下摆分叉让布料真实覆盖靴子而非方裙
    p.poly([(cx-19,57),(cx+18,57),(cx+24,105),(cx+12,110),
            (cx+2,106),(cx-12,112),(cx-25,106)],'teal0')
    p.poly([(cx-18,59),(cx+14,58),(cx+20,102),(cx+9,107),
            (cx-2,103),(cx-18,108),(cx-21,101)],'teal2')
    p.poly([(cx-16,59),(cx-10,57),(cx-10,103),(cx-19,105)],'teal3')
    p.poly([(cx+10,63),(cx+16,63),(cx+19,102),(cx+9,104)],'teal1')
    p.line([(cx-15,64),(cx-16,99)],'teal5',2)
    p.line([(cx-5,82),(cx-8,108)],'teal1',3)
    p.line([(cx+7,87),(cx+10,105)],'teal0',2)
    # 顶部袍身和立领
    p.poly([(cx-21,59),(cx-13,47),(cx-6,48),(cx,58),(cx+5,48),
            (cx+14,49),(cx+20,60),(cx+17,83),(cx-20,83)],'teal1')
    p.poly([(cx-18,58),(cx-12,52),(cx-8,57),(cx-8,80),(cx-18,81)],'teal3')
    p.poly([(cx+10,52),(cx+18,60),(cx+15,81),(cx+8,80)],'teal2')
    p.poly([(cx-7,48),(cx+1,60),(cx+6,49),(cx+11,50),
            (cx+3,65),(cx-6,57)],'ivory2')
    p.line([(cx-8,49),(cx+2,67)],'teal0',3)
    p.line([(cx+9,49),(cx-1,65)],'ivory3',2)
    p.line([(cx-4,63),(cx+7,77)],'teal4',2)
    # 细腰封、铜扣和悬带
    p.rect((cx-19,77,cx+18,83),'ivory0')
    p.line([(cx-18,78),(cx+18,78)],'ivory3',2)
    p.rect((cx-5,77,cx+5,83),'gold1')
    p.rect((cx-3,78,cx+3,81),'gold4')
    p.dot(cx,79,'gold5')
    p.line([(cx+6,82),(cx+9,94)],'ivory2',3)
    p.line([(cx+6,90),(cx+10,95)],'gold2')
    # 袍裾暗纹和绣边，控形而非随机散点
    p.line([(cx-20,104),(cx-12,107),(cx-6,105)],'teal4',2)
    p.line([(cx+3,105),(cx+11,107),(cx+19,103)],'teal4',2)
    for x,y in ((cx-12,91),(cx+10,95),(cx-1,100)):
        p.line([(x,y),(x+3,y-2),(x+6,y)],'teal4')


def build_stage1_scholar(frame:int):
    f=frame%4;p=PixelCanvas();cx=65
    _coat_scholar(p,cx,f)
    if f==0:
        _arm(p,(cx-17,57),(cx-27,70),(cx-25,89),'scholar')
        _arm(p,(cx+17,57),(cx+26,68),(cx+32,78),'scholar')
        _scroll(p,cx+30,65)
    elif f==1:
        _arm(p,(cx-17,57),(cx-29,67),(cx-27,86),'scholar')
        _arm(p,(cx+17,57),(cx+24,52),(cx+34,58),'scholar')
        _scroll(p,cx+30,45)
    elif f==2:
        _arm(p,(cx-17,57),(cx-28,71),(cx-24,87),'scholar')
        _arm(p,(cx+17,57),(cx+29,47),(cx+40,40),'scholar')
        p.line([(cx+41,39),(cx+52,20)],'brown3',3)
        p.line([(cx+51,21),(cx+55,19)],'hair0',4)
        _scroll(p,99,65,True)
    else:
        _arm(p,(cx-17,57),(cx-21,75),(cx-10,87),'scholar')
        _arm(p,(cx+17,57),(cx+23,75),(cx+10,86),'scholar')
    _face(p,cx,25 if f!=1 else 24,'scholar','angry' if f in (1,2) else 'stern',turn=f==3)
    # 菊花不是单像素飘点，做 8 花瓣造型
    if f in (1,3):
        x,y=(24,98) if f==3 else (23,31)
        for dx,dy in ((0,-6),(5,-3),(6,2),(4,6),(-1,6),(-5,3),(-5,-3),(-1,-4)):
            p.line([(x,y),(x+dx,y+dy)],'gold3',3)
            p.dot(x+dx,y+dy,'gold5')
        p.ell((x-3,y-3,x+3,y+3),'gold1')
    return _image_to_grid(p.finish())


def _armor_rebel(p,cx,step=0):
    _boots(p,cx,step,False)
    p.poly([(cx-21,74),(cx+19,74),(cx+21,99),(cx+11,102),
            (cx+2,96),(cx-13,103),(cx-22,98)],'brown0')
    p.poly([(cx-17,80),(cx+16,80),(cx+16,97),(cx+7,98),(cx-4,94),(cx-16,99)],'brown2')
    for xx in (cx-14,cx-4,cx+7):
        p.poly([(xx,83),(xx+8,83),(xx+9,94),(xx+4,98),(xx-2,94)],'brown3')
        p.line([(xx+1,85),(xx+6,85)],'brown4',2)
        p.dot(xx+3,92,'gold2')
    p.poly([(cx-21,56),(cx-14,49),(cx+12,49),(cx+21,57),
            (cx+19,84),(cx-20,84)],'brown0')
    p.poly([(cx-18,57),(cx-12,52),(cx+10,52),(cx+17,58),
            (cx+14,80),(cx-17,80)],'brown2')
    p.poly([(cx-17,56),(cx-10,53),(cx-7,78),(cx-18,77)],'brown3')
    p.poly([(cx+7,54),(cx+13,56),(cx+14,77),(cx+7,79)],'brown1')
    # 三行札甲每片分界、铆钉及错列，消除大块纯色
    for row,y in enumerate((60,68,76)):
        for col,x in enumerate((cx-13,cx-5,cx+3,cx+11)):
            xx=x+(3 if row%2 else 0)
            if xx>cx+14: continue
            p.poly([(xx-4,y),(xx+3,y),(xx+4,y+6),(xx-3,y+6)],'brown1' if (row+col)%2 else 'brown3')
            p.line([(xx-3,y+1),(xx+2,y+1)],'brown4')
            p.dot(xx,y+3,'gold3')
    p.line([(cx-12,51),(cx+4,72)],'brown0',5)
    p.line([(cx-10,52),(cx+3,68)],'brown4',2)
    p.rect((cx-21,80,cx+20,86),'red0')
    p.line([(cx-19,80),(cx+17,80)],'red4',2)
    p.rect((cx-5,80,cx+6,86),'gold1')
    p.rect((cx-3,81,cx+4,84),'gold4')
    p.line([(cx-2,86),(cx-5,101)],'red3',5)
    p.line([(cx+5,86),(cx+9,97)],'red1',4)
    for x in (cx-16,cx+14):p.dot(x,83,'gold4')


def build_stage2_rebel(frame:int):
    f=frame%4;p=PixelCanvas();cx=76 if f!=3 else 78
    _flag(p,14,12,'rebel',phase=f)
    _armor_rebel(p,cx,4 if f==3 else 0)
    _arm(p,(cx-18,58),(cx-31,68),(18,75),'rebel')
    # 握旗杆的手交叠在旗杆上
    p.rect((14,72,22,78),'skin2');p.line([(16,72),(21,73)],'skin4',2)
    if f==0:
        _arm(p,(cx+18,58),(cx+28,73),(cx+27,84),'rebel')
        _sword(p,(cx+27,84),(cx+33,113))
    elif f==1:
        _arm(p,(cx+18,58),(cx+30,58),(cx+36,50),'rebel')
        _sword(p,(cx+36,50),(121,17))
    elif f==2:
        _arm(p,(cx+18,58),(cx+26,45),(cx+27,36),'rebel')
        _sword(p,(cx+27,36),(108,5))
    else:
        _arm(p,(cx+18,58),(cx+28,65),(cx+34,65),'rebel')
        _sword(p,(cx+34,65),(124,59))
    _face(p,cx,25 if f!=3 else 26,'bandana','angry')
    return _image_to_grid(p.finish())


def _armor_general(p,cx,wind=0,step=0):
    _boots(p,cx,step,True)
    # 披风是后层：可分辨背光、内衬、迎风高光与撕裂的锯齿边缘
    p.poly([(cx-16,52),(cx-25,60),(cx-30-wind,82),(cx-39-wind,112),
            (cx-27-wind,108),(cx-22,115),(cx-17,100),(cx-10,67)],'red0')
    p.poly([(cx-17,54),(cx-25,63),(cx-29-wind,91),(cx-33-wind,106),
            (cx-23-wind,103),(cx-17,88)],'red2')
    p.line([(cx-23,62),(cx-25-wind,97),(cx-29-wind,105)],'red4',3)
    p.poly([(cx-22,78),(cx+22,78),(cx+20,103),(cx+9,107),
            (cx-4,101),(cx-17,107)],'iron0')
    for xx in (cx-14,cx-6,cx+3,cx+12):
        p.poly([(xx-4,82),(xx+5,82),(xx+7,98),(xx+1,102),(xx-4,98)],'iron2')
        p.line([(xx-3,84),(xx+4,84)],'iron4',2)
        p.dot(xx+1,96,'gold3')
    p.poly([(cx-23,57),(cx-14,49),(cx+13,49),(cx+23,57),
            (cx+20,83),(cx-21,83)],'iron0')
    p.poly([(cx-19,57),(cx-13,53),(cx+11,53),(cx+20,58),
            (cx+17,80),(cx-19,80)],'iron2')
    # 鎏金肩甲 + 兽头装饰：多层铆片
    for s in (-1,1):
        x=cx+s*17
        p.poly([(x-9,52),(x+7,52),(x+10,59),(x+7,65),
                (x-6,65),(x-11,59)],'iron0')
        p.poly([(x-7,53),(x+5,53),(x+8,58),(x+4,63),(x-6,62)],'iron4')
        p.line([(x-5,55),(x+4,55)],'steel3',2)
        p.poly([(x-2,58),(x,57),(x+3,58),(x+2,61),(x-1,62)],'gold2')
        p.dot(x,59,'gold5')
    # 胸口明光镜以椭圆反射塑造立体金属
    for x in (cx-9,cx+7):
        p.ell((x-8,60,x+8,78),'iron1')
        p.ell((x-6,62,x+6,76),'iron3')
        p.poly([(x-3,64),(x+2,63),(x+5,66),(x+2,70),(x-3,69)],'steel2')
        p.line([(x-2,64),(x+1,64)],'steel3',2)
        p.dot(x+4,73,'iron0')
    p.line([(cx,60),(cx,80)],'iron0',3)
    p.rect((cx-22,79,cx+21,86),'gold0')
    p.line([(cx-20,80),(cx+19,80)],'gold4',2)
    p.rect((cx-5,79,cx+6,86),'gold2')
    p.rect((cx-3,80,cx+4,84),'gold5')
    for x in (cx-15,cx+14):p.dot(x,82,'gold5')


def build_stage3_chongtian(frame:int):
    f=frame%4;p=PixelCanvas();cx=68
    _armor_general(p,cx,(0,4,9,6)[f],3 if f==2 else 0)
    _arm(p,(cx-18,58),(cx-30,70),(cx-24,86),'general')
    if f==0:
        _arm(p,(cx+18,58),(cx+29,66),(cx+35,72),'general')
        _spear(p,(cx+34,115),(cx+36,26))
    elif f==1:
        _arm(p,(cx+18,58),(cx+30,49),(cx+34,41),'general')
        _spear(p,(44,111),(104,21))
    elif f==2:
        _arm(p,(cx+18,58),(cx+31,60),(cx+38,63),'general')
        _spear(p,(17,75),(105,55))
    else:
        _arm(p,(cx+18,58),(cx+28,50),(cx+36,42),'general')
        _spear(p,(39,109),(108,25))
    _face(p,cx,29,'helmet','angry' if f in (2,3) else 'stern')
    return _image_to_grid(p.finish())


def _dragon(p,cx,y):
    """胸口清晰可读的金线盘龙：首、角、爪、反卷的尾和火珠。"""
    p.line([(cx-12,y-1),(cx-4,y-4),(cx+8,y-2),(cx+13,y+4),
            (cx+9,y+9),(cx-1,y+10),(cx-6,y+14),(cx+2,y+19),
            (cx+11,y+16)],'gold0',5)
    p.line([(cx-12,y-2),(cx-4,y-5),(cx+7,y-3),(cx+11,y+3),
            (cx+8,y+7),(cx-1,y+8),(cx-5,y+13),(cx+2,y+17),
            (cx+10,y+14)],'gold5',2)
    p.poly([(cx-13,y-3),(cx-17,y-6),(cx-19,y-2),(cx-14,y+1)],'gold4')
    p.line([(cx-15,y-4),(cx-18,y-8)],'gold5',2)
    p.line([(cx-12,y-4),(cx-12,y-9)],'gold5',2)
    p.dot(cx-15,y-2,'red3')
    p.line([(cx+8,y+4),(cx+15,y+3)],'gold4',2)
    p.line([(cx+1,y+9),(cx+3,y+14)],'gold5',2)
    p.line([(cx-2,y+16),(cx-7,y+19)],'gold4',2)
    p.ell((cx-21,y+5,cx-15,y+11),'red3')
    p.dot(cx-18,y+6,'gold5')


def _emperor_robe(p,cx,spread=0):
    _boots(p,cx,0,False)
    # 玄红内衬 + 裙摆分层，并用折边强调丝绸垂坠
    p.poly([(cx-20,66),(cx+20,66),(cx+30+spread,113),(cx+14,118),
            (cx+1,109),(cx-13,119),(cx-28-spread,112)],'red0')
    p.poly([(cx-20,65),(cx+19,65),(cx+27+spread,111),(cx+15,115),
            (cx+2,106),(cx-14,115),(cx-26-spread,111)],'gold1')
    p.poly([(cx-15,68),(cx+14,68),(cx+20+spread,110),(cx+5,111),
            (cx-3,105),(cx-18,111)],'gold3')
    p.poly([(cx-15,68),(cx-7,69),(cx-12,110),(cx-20,111)],'gold4')
    p.line([(cx-24-spread,111),(cx-14,114),(cx-7,112)],'gold5',2)
    p.line([(cx+6,111),(cx+15,115),(cx+24+spread,111)],'gold5',2)
    p.line([(cx-6,87),(cx-6,110)],'gold1',3)
    p.line([(cx+9,83),(cx+14,111)],'gold2',3)
    # 身躯金色衣表和赤色交领
    p.poly([(cx-23,55),(cx-15,47),(cx-8,48),(cx,56),(cx+7,48),
            (cx+15,49),(cx+23,55),(cx+21,88),(cx-22,88)],'gold1')
    p.poly([(cx-20,54),(cx-14,51),(cx-7,52),(cx-7,85),(cx-20,85)],'gold4')
    p.poly([(cx+8,51),(cx+18,55),(cx+19,85),(cx+10,86)],'gold2')
    p.poly([(cx-8,47),(cx,59),(cx+7,48),(cx+10,50),(cx+1,67),(cx-11,51)],'red0')
    p.line([(cx-9,48),(cx+1,67)],'gold5',3)
    p.line([(cx+10,49),(cx+1,66)],'red4',2)
    # 胸口盘龙占 30x27px，有真实分节高光
    _dragon(p,cx,64)
    p.rect((cx-22,85,cx+21,92),'red1')
    p.line([(cx-20,86),(cx+20,86)],'red4',2)
    p.rect((cx-6,84,cx+7,92),'gold0')
    p.rect((cx-4,85,cx+5,90),'gold4')
    p.dot(cx,87,'red3')
    # 下摆云纹取形于卷曲线条，而非一排均匀方块
    for xx,yy in ((cx-17,104),(cx-2,108),(cx+13,104)):
        p.line([(xx-5,yy+3),(xx-2,yy),(xx+1,yy+1),
                (xx+3,yy-2),(xx+6,yy-1)],'gold5',2)
    for xx in (cx-15,cx+14):
        p.line([(xx,67),(xx+3,75)],'gold5')
        p.dot(xx+3,77,'gold1')


def build_stage4_emperor(frame:int):
    f=frame%4;p=PixelCanvas();cx=76
    _flag(p,13,12,'empire',phase=f)
    _emperor_robe(p,cx,3 if f==3 else 0)
    _arm(p,(cx-20,58),(cx-31,75),(cx-22,87),'emperor')
    if f==0:
        _arm(p,(cx+19,57),(cx+30,74),(cx+18,87),'emperor')
        p.poly([(cx-11,83),(cx+9,83),(cx+9,91),(cx-11,91)],'ivory1')
        p.rect((cx-9,84,cx+7,89),'ivory3')
        p.line([(cx-4,86),(cx+5,86)],'ivory0')
    elif f==1:
        _arm(p,(cx+20,57),(cx+30,72),(cx+32,86),'emperor')
        _sword(p,(cx+32,84),(cx+34,119))
    elif f==2:
        _arm(p,(cx+20,57),(cx+30,49),(cx+35,38),'emperor')
        p.line([(cx+32,36),(cx+38,33)],'skin4',3)
    else:
        _arm(p,(cx+20,57),(cx+29,73),(cx+18,87),'emperor')
        for x,y in ((114,27),(107,97),(55,17)):
            p.line([(x-2,y+2),(x,y-2),(x+2,y+2)],'gold5')
    _face(p,cx,30,'crown')
    return _image_to_grid(p.finish())


def _wounded_armor(p,cx,lean=0):
    _boots(p,cx,4 if lean else 0,True)
    # 破损披风露出深铁甲，错乱的衣片与缺口保持画面完整
    p.poly([(cx-19,55),(cx-29,70),(cx-36,106),(cx-25,105),
            (cx-17,97),(cx-13,66)],'red0')
    p.poly([(cx-20,56),(cx-27,74),(cx-31,100),(cx-24,97)],'red2')
    p.poly([(cx-21,78),(cx+16,78),(cx+20,105),(cx+5,104),
            (cx-12,109),(cx-22,101)],'iron0')
    p.poly([(cx-13,84),(cx+15,84),(cx+15,99),(cx-9,102)],'gold0')
    p.poly([(cx-20,56),(cx-14,49),(cx+13,50),(cx+23,58),
            (cx+16,83),(cx-21,83)],'iron0')
    p.poly([(cx-18,54),(cx-12,52),(cx+13,53),(cx+18,60),
            (cx+13,80),(cx-16,79)],'gold1')
    p.poly([(cx-18,55),(cx-11,54),(cx-12,78),(cx-18,76)],'gold3')
    p.poly([(cx-4,61),(cx+12,58),(cx+11,71),(cx+3,76),(cx-3,69)],'gold3')
    p.line([(cx-3,61),(cx+7,65)],'gold5',2)
    p.poly([(cx-13,63),(cx-5,65),(cx-7,73),(cx-14,76)],'iron1')
    p.poly([(cx+6,70),(cx+18,71),(cx+14,83),(cx+4,80)],'iron2')
    p.line([(cx-11,67),(cx-3,76)],'blood',4)
    p.line([(cx-9,68),(cx-5,72)],'bloodlight',2)
    p.line([(cx+13,62),(cx+10,76)],'blood',3)
    p.line([(cx+7,88),(cx+10,99)],'blood',2)
    # 残存旧帝袍细纹
    p.line([(cx-16,95),(cx-11,97),(cx-5,96)],'gold3')
    p.line([(cx+3,93),(cx+9,92)],'gold2')
    p.rect((cx-21,81,cx+19,87),'red0')
    p.rect((cx-5,81,cx+5,87),'gold1')
    p.dot(cx,84,'gold4')
    for x,y in ((cx-16,66),(cx+15,76),(cx-9,102),(cx+12,105)):
        p.dot(x,y,'dust1');p.dot(x+2,y+1,'dust2')


def _fallen(p,cx):
    # 第 4 帧为独立卧倒动作，不复用站立方块模型
    p.poly([(cx-35,94),(cx-10,85),(cx+17,90),(cx+39,104),
            (cx+28,113),(cx-17,110),(cx-39,105)],'iron0')
    p.poly([(cx-30,92),(cx-8,87),(cx+15,94),(cx+32,103),
            (cx+16,108),(cx-24,104)],'gold1')
    p.poly([(cx-26,92),(cx-8,88),(cx+6,93),(cx+11,99),
            (cx-15,103),(cx-25,100)],'gold3')
    p.line([(cx-22,98),(cx-5,101)],'blood',4)
    p.poly([(cx-31,92),(cx-33,83),(cx-20,77),(cx-12,80),
            (cx-9,89),(cx-17,96)],'hair0')
    p.poly([(cx-29,85),(cx-21,81),(cx-15,83),(cx-15,90),
            (cx-22,93),(cx-28,90)],'skin2')
    p.line([(cx-29,86),(cx-25,85)],'skin4',2)
    p.rect((cx-18,86,cx-15,88),'hair0')
    p.line([(cx-22,91),(cx-17,94)],'hair0',3)
    p.line([(cx-12,93),(cx-7,97)],'hair2',2)
    # 错位护腿和脱手的剑
    p.poly([(cx+14,102),(cx+31,100),(cx+36,107),(cx+22,112)],'iron1')
    p.poly([(cx+29,104),(cx+42,108),(cx+42,115),(cx+32,116)],'brown0')
    _sword(p,(cx+9,113),(cx+56,120))


def build_stage5_langhugu(frame:int):
    f=frame%4;p=PixelCanvas()
    # 草屑是角色所在区域的透明舞台元素，不额外铺背景
    for x,y in ((7,118),(15,121),(28,121),(103,120),(115,118)):
        p.line([(x,y),(x-2,y-7)],'dust1')
        p.line([(x,y),(x+3,y-5)],'dust2')
    _flag(p,13,19,'empire',broken=True)
    if f==3:
        _fallen(p,68)
    else:
        cx=76 if f!=0 else 78
        _wounded_armor(p,cx,lean=f==0)
        if f==0:
            _arm(p,(cx-18,58),(cx-32,70),(cx-31,89),'wounded')
            _arm(p,(cx+18,58),(cx+28,75),(cx+29,90),'wounded')
            _sword(p,(cx+29,88),(cx+33,120))
        elif f==1:
            _arm(p,(cx-18,58),(cx-30,70),(cx-22,86),'wounded')
            _arm(p,(cx+18,58),(cx+27,74),(cx+31,85),'wounded')
            _sword(p,(cx+31,84),(cx+43,117))
        else:
            _arm(p,(cx-18,58),(cx-33,66),(cx-42,64),'wounded')
            _arm(p,(cx+18,58),(cx+27,51),(cx+34,47),'wounded')
            _sword(p,(cx+34,47),(123,23))
        _face(p,cx,30+(2 if f==0 else 0),'wounded','angry' if f==2 else 'stern',turn=f==1)
    return _image_to_grid(p.finish())


# 保留上一版的二维网格数据结构和名称，供旧的 Pillow/FFmpeg 管线继续调用。
# 每个单元格存放可直接在 PALETTE 中查询的材质色号。
_REVERSE = {color:key for key,color in RGB.items()}
def _image_to_grid(image:Image.Image)->List[List[str]]:
    px=image.load()
    return [[_REVERSE.get(px[x,y],'ink' if px[x,y][3] else 'none')
             for x in range(image.width)] for y in range(image.height)]

# 外轮廓 alpha 由算法生成后，可能出现与 palette 不同的纯黑不透明像素。
# _image_to_grid 里映射为 ink，仍保留全部细节和透明通道。

def grid_to_image(grid,scale:int=1)->Image.Image:
    if not isinstance(scale,int) or scale<1: raise ValueError('scale 必须是正整数')
    if isinstance(grid,Image.Image): out=grid.convert('RGBA')
    else:
        h=len(grid);w=len(grid[0]);out=Image.new('RGBA',(w,h));px=out.load()
        for y,row in enumerate(grid):
            for x,key in enumerate(row):px[x,y]=PALETTE[key]
    return out if scale==1 else out.resize((out.width*scale,out.height*scale),Image.Resampling.NEAREST)

STAGES = [
    {'key':'S1_SCHOLAR','title':'阶段 I · 落第赋菊','year':'874 岁末 · 长安曲江',
     'desc':'翅角幞头 · 青衫交领 · 织边襕袍 · 诗卷金菊',
     'frames':['执卷凝视','怒握榜文','掷笔碎榜','背手望宫'],'builder':build_stage1_scholar,'bg':(27,48,58)},
    {'key':'S2_REBEL','title':'阶段 II · 冤句起兵','year':'875 仲夏 · 曹州起兵',
     'desc':'赤巾飘带 · 三列札甲 · 皮革铆钉 · 黑红义旗',
     'frames':['按剑立誓','拔剑出鞘','挥剑指天','迈步起义'],'builder':build_stage2_rebel,'bg':(55,37,44)},
    {'key':'S3_CHONGTIAN','title':'阶段 III · 冲天转战','year':'878–880 · 转战万里',
     'desc':'鎏金兽肩 · 明光镜甲 · 玄铁护腿 · 猩红披风',
     'frames':['驻槊远眺','扬槊指路','平端突刺','挥槊斩阵'],'builder':build_stage3_chongtian,'bg':(37,45,62)},
    {'key':'S4_EMPEROR','title':'阶段 IV · 含元登基','year':'881 正月 · 大齐皇帝',
     'desc':'金冕垂珠 · 盘龙云纹 · 绛色内衬 · 明黄帝袍',
     'frames':['登陛受朝','按剑威严','抬臂号令','孤城流光'],'builder':build_stage4_emperor,'bg':(63,47,32)},
    {'key':'S5_LANGHUGU','title':'阶段 V · 狼虎末路','year':'884 盛夏 · 泰山狼虎谷',
     'desc':'披发血痕 · 裂甲伤痕 · 金袍破损 · 折旗落幕',
     'frames':['拄剑喘息','回望泰山','横剑决绝','折旗落幕'],'builder':build_stage5_langhugu,'bg':(48,37,44)}
]


def get_huangchao_sprite(stage_key:str,frame:int=0,scale:int=4)->Image.Image:
    for st in STAGES:
        if st['key']==stage_key:
            return grid_to_image(st['builder'](frame%4),scale)
    raise ValueError(f'Unknown stage_key={stage_key!r}; options={[s["key"] for s in STAGES]}')


def _font(size,bold=False):
    names=(['/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc','/usr/share/fonts/truetype/noto/NotoSerifCJK-Bold.ttc'] if bold else
           ['/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc','/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
    for name in names:
        if Path(name).exists():return ImageFont.truetype(name,size)
    return ImageFont.load_default()


def render_sprite_sheet(output_dir=OUT):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    gap=8; atlas=Image.new('RGBA',((SIZE+gap)*4,(SIZE+gap)*5))
    for r,stage in enumerate(STAGES):
        for c in range(4):
            atlas.alpha_composite(get_huangchao_sprite(stage['key'],c,1),(c*(SIZE+gap),r*(SIZE+gap)))
    f=output_dir/'huangchao_sprite_atlas_128px.png';atlas.save(f);return f


def render_showcase_and_gif(output_dir=OUT):
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    wide=1660;h=1240
    board=Image.new('RGB',(wide,h),(19,21,29));d=ImageDraw.Draw(board)
    title=_font(37,True);sub=_font(19);label=_font(19,True);small=_font(16)
    d.text((38,20),'《黄巢五幕》· V3 原生 128×128 高精像素人物',fill=(255,224,151),font=title)
    d.text((40,74),'重绘面部、比例、材质与服饰结构 / 五种身份 × 四种独立动作 / 透明底可用于游戏及动画',fill=(185,193,199),font=sub)
    d.line([(39,112),(1620,112)],fill=(173,133,73),width=2)
    gif=[]
    for row,st in enumerate(STAGES):
        y=132+row*220; bg=st['bg']
        d.rounded_rectangle([31,y,wide-31,y+203],radius=15,fill=(29,31,40),outline=(73,76,85),width=2)
        d.text((52,y+16),st['title'],font=label,fill=(247,212,137))
        d.text((52,y+47),st['year'],font=sub,fill=(213,135,117))
        d.text((52,y+82),st['desc'],font=small,fill=(189,201,205))
        for col in range(4):
            x=450+col*300
            d.rounded_rectangle((x,y+11,x+277,y+188),radius=10,fill=bg,outline=(92,92,96),width=2)
            spr=get_huangchao_sprite(st['key'],col,1).resize((160,160),Image.Resampling.NEAREST)
            board.paste(spr,(x+55,y+8),spr)
            d.text((x+15,y+166),f'F{col+1}   {st["frames"][col]}',font=small,fill=(241,235,222))
            gf=Image.new('RGBA',(440,430),(23,25,32));gd=ImageDraw.Draw(gf)
            gd.rounded_rectangle((17,15,423,414),radius=18,fill=bg,outline=(180,145,82),width=3)
            gd.text((36,27),st['title'],font=label,fill=(250,214,140))
            gd.text((37,58),st['frames'][col],font=sub,fill=(220,216,206))
            gspr=get_huangchao_sprite(st['key'],col,2)
            gf.alpha_composite(gspr,((440-gspr.width)//2,105))
            gif.append(gf.convert('RGB'))
    preview=output_dir/'huangchao_pixel_showcase_ultra.png';board.save(preview,optimize=True)
    anim=output_dir/'huangchao_turning_points_ultra.gif'
    gif[0].save(anim,save_all=True,append_images=gif[1:],duration=400,loop=0,disposal=2,optimize=False)
    return preview,anim

if __name__=='__main__':
    print('atlas:',render_sprite_sheet())
    print('showcase, gif:',render_showcase_and_gif())
