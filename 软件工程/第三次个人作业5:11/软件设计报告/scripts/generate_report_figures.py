from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "figures"
OUT_DIR.mkdir(parents=True, exist_ok=True)

WIDTH = 1900
HEIGHT = 1080
BG = "#FFFFFF"
LINE = "#4F6F99"
TEXT = "#26323F"
SUBTLE = "#6E8199"
SHADOW = "#D9E0EA"


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
    ]
    index = 1 if bold else 0
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size, index=index)
        except OSError:
            continue
    return ImageFont.load_default()


FONT = load_font(30)
FONT_SMALL = load_font(24)
FONT_BOLD = load_font(34, bold=True)
FONT_TINY = load_font(20)


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int
    text: str
    fill: str
    outline: str = LINE
    radius: int = 26
    text_font: ImageFont.FreeTypeFont = FONT

    def center(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h // 2)

    def top(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y)

    def bottom(self) -> tuple[int, int]:
        return (self.x + self.w // 2, self.y + self.h)

    def left(self) -> tuple[int, int]:
        return (self.x, self.y + self.h // 2)

    def right(self) -> tuple[int, int]:
        return (self.x + self.w, self.y + self.h // 2)


def canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((38, 40, WIDTH - 38, HEIGHT - 48), radius=32, outline="#E5E9F0", width=3)
    return image, draw


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    paragraphs = text.split("\n")
    lines: list[str] = []
    for para in paragraphs:
        buf = ""
        for ch in para:
            trial = buf + ch
            bbox = draw.textbbox((0, 0), trial, font=font)
            if bbox[2] - bbox[0] <= max_width or not buf:
                buf = trial
            else:
                lines.append(buf)
                buf = ch
        if buf:
            lines.append(buf)
    return lines


def draw_box(draw: ImageDraw.ImageDraw, box: Box) -> None:
    shadow_offset = 8
    draw.rounded_rectangle(
        (box.x + shadow_offset, box.y + shadow_offset, box.x + box.w + shadow_offset, box.y + box.h + shadow_offset),
        radius=box.radius,
        fill=SHADOW,
    )
    draw.rounded_rectangle(
        (box.x, box.y, box.x + box.w, box.y + box.h),
        radius=box.radius,
        fill=box.fill,
        outline=box.outline,
        width=4,
    )
    lines = wrap_text(draw, box.text, box.text_font, box.w - 38)
    line_h = draw.textbbox((0, 0), "测", font=box.text_font)[3] + 10
    total_h = line_h * len(lines)
    y = box.y + (box.h - total_h) // 2 - 4
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=box.text_font)
        x = box.x + (box.w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=TEXT, font=box.text_font)
        y += line_h


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], width: int = 5) -> None:
    draw.line((start, end), fill=LINE, width=width)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    if dx == 0 and dy == 0:
        return
    import math

    angle = math.atan2(dy, dx)
    size = 18
    left = (
        end[0] - size * math.cos(angle) + size * 0.55 * math.sin(angle),
        end[1] - size * math.sin(angle) - size * 0.55 * math.cos(angle),
    )
    right = (
        end[0] - size * math.cos(angle) - size * 0.55 * math.sin(angle),
        end[1] - size * math.sin(angle) + size * 0.55 * math.cos(angle),
    )
    draw.polygon([end, left, right], fill=LINE)


def elbow(draw: ImageDraw.ImageDraw, points: Iterable[tuple[int, int]], width: int = 5) -> None:
    pts = list(points)
    for a, b in zip(pts, pts[1:]):
        draw.line((a, b), fill=LINE, width=width)
    if len(pts) >= 2:
        arrow(draw, pts[-2], pts[-1], width=width)


def note(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, fill: str = "#FFF5D9") -> None:
    x, y = xy
    w, h = 240, 82
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=fill, outline="#C9B16E", width=3)
    lines = wrap_text(draw, text, FONT_TINY, w - 22)
    line_h = 26
    yy = y + 15
    for line in lines:
        draw.text((x + 14, yy), line, fill="#6B5A2C", font=FONT_TINY)
        yy += line_h


def save(image: Image.Image, name: str) -> None:
    image.save(OUT_DIR / name, quality=95)


def system_overview() -> None:
    image, draw = canvas()
    top = Box(670, 110, 460, 110, "统一登录与身份认证", "#EAF1FB")
    split = Box(635, 280, 530, 120, "角色识别、权限校验\n与工作台分流", "#EDF4FF")
    modeler = Box(100, 520, 380, 150, "场景建模师\n创建项目、编辑布局、生成场景", "#E9F2FF")
    analyst = Box(710, 520, 380, 150, "行业分析师\n查看结果、运行仿真、导出分析", "#EEF8EA")
    admin = Box(1320, 520, 380, 150, "系统管理员\n维护用户、配置服务、审计日志", "#FFF1E6")
    out = Box(635, 785, 530, 110, "结果保存、版本留存、导出输出\n与关键操作日志记录", "#F8F3EA")
    for b in [top, split, modeler, analyst, admin, out]:
        draw_box(draw, b)
    arrow(draw, top.bottom(), split.top())
    elbow(draw, [split.bottom(), (split.bottom()[0], 455), modeler.top()])
    arrow(draw, split.bottom(), analyst.top())
    elbow(draw, [split.bottom(), (split.bottom()[0], 455), admin.top()])
    elbow(draw, [modeler.bottom(), (modeler.center()[0], 720), (760, 720), out.left()])
    arrow(draw, analyst.bottom(), out.top())
    elbow(draw, [admin.bottom(), (admin.center()[0], 720), (1040, 720), out.right()])
    note(draw, (92, 705), "核心生产路径")
    note(draw, (1462, 705), "治理与维护路径", fill="#FFEEDC")
    save(image, "system_overview.png")


def vertical_flow(name: str, fill: str, labels: list[str], side_notes: list[tuple[int, str]]) -> None:
    image, draw = canvas()
    boxes: list[Box] = []
    x = 630
    y = 105
    for idx, label in enumerate(labels):
        h = 92 if idx not in {2, 3} else 108
        boxes.append(Box(x, y, 540, h, label, fill))
        y += h + 42
    for b in boxes:
        draw_box(draw, b)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, a.bottom(), b.top())
    if len(boxes) >= 5:
        elbow(draw, [boxes[4].left(), (430, boxes[4].center()[1]), (430, boxes[2].center()[1]), boxes[2].left()])
        note(draw, (120, boxes[3].y + 15), "支持多轮调整\n与重新提交")
    for idx, text in side_notes:
        target = boxes[idx]
        note(draw, (1240, target.y + 10), text, fill="#EEF7FF")
        elbow(draw, [target.right(), (1210, target.center()[1]), (1210, target.center()[1]), (1240, target.center()[1])], width=4)
    save(image, name)


def asset_replace_flow() -> None:
    image, draw = canvas()
    boxes = [
        Box(75, 370, 260, 120, "选择模板场景\n或空白场景", "#FFF2E7"),
        Box(400, 370, 260, 120, "检索道路、建筑\n树木等候选资产", "#FFF6EC"),
        Box(725, 350, 320, 160, "根据资产类别联动\n展示参数与约束项", "#FFF7EE"),
        Box(1110, 370, 260, 120, "调用插件执行\n生成或替换", "#FFF2E7"),
        Box(1435, 370, 290, 120, "结果回显、差异比对\n与用户确认", "#FFF6EC"),
    ]
    for b in boxes:
        draw_box(draw, b)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, a.right(), b.left())
    review = Box(1115, 670, 255, 105, "不满足预期时\n重新配置参数", "#FFF1E4", text_font=FONT_SMALL)
    draw_box(draw, review)
    elbow(draw, [boxes[-1].bottom(), (boxes[-1].center()[0], 615), review.right()])
    elbow(draw, [review.left(), (1030, review.center()[1]), (1030, boxes[2].center()[1]), boxes[2].bottom()])
    note(draw, (720, 120), "参数联动可减少\n不匹配资产组合")
    note(draw, (1440, 135), "支持确认后保存\n为场景新版本", fill="#EEF8EA")
    save(image, "asset_replace_flow.png")


def layout_ecology_flow() -> None:
    image, draw = canvas()
    boxes = [
        Box(80, 360, 250, 130, "输入控制点、\n线集或上传草图", "#EAF7F8"),
        Box(395, 360, 260, 130, "提取道路边界、\n分区轮廓和水域范围", "#EDF9FA"),
        Box(720, 350, 330, 150, "生成中间布局结果\n并允许人工校正", "#E6F6F7"),
        Box(1115, 360, 265, 130, "生成山体、湖泊、\n绿化和船只等对象", "#EDF9FA"),
        Box(1445, 360, 250, 130, "更新场景并同步\n到仿真与视图", "#EAF7F8"),
    ]
    for b in boxes:
        draw_box(draw, b)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, a.right(), b.left())
    revise = Box(735, 665, 300, 100, "识别误差校正后\n再次生成布局", "#E7F8F4", text_font=FONT_SMALL)
    draw_box(draw, revise)
    elbow(draw, [boxes[2].bottom(), (boxes[2].center()[0], 610), revise.top()])
    elbow(draw, [revise.right(), (1090, revise.center()[1]), (1090, boxes[1].center()[1]), boxes[1].bottom()])
    note(draw, (390, 125), "保留中间结果，避免\n草图识别直接覆盖场景")
    save(image, "layout_ecology_flow.png")


def llm_sim_flow() -> None:
    image, draw = canvas()
    boxes = [
        Box(70, 365, 260, 125, "输入自然语言、\n草图或参数组合", "#FFF0F0"),
        Box(390, 350, 300, 155, "LLM 识别对象、属性、\n数量、空间关系和修改意图", "#FFF4F4"),
        Box(750, 350, 300, 155, "拆解为结构化子任务\n并匹配插件能力", "#FFF7F7"),
        Box(1110, 350, 260, 155, "执行建模与动态对象\n配置任务", "#FFF4F4"),
        Box(1430, 365, 270, 125, "展示仿真结果、\n提示调整建议", "#FFF0F0"),
    ]
    for b in boxes:
        draw_box(draw, b)
    for a, b in zip(boxes, boxes[1:]):
        arrow(draw, a.right(), b.left())
    fallback = Box(760, 665, 290, 100, "解析歧义时提示用户\n补充约束或改写指令", "#FFF6E7", text_font=FONT_SMALL)
    draw_box(draw, fallback)
    elbow(draw, [boxes[2].bottom(), (boxes[2].center()[0], 610), fallback.top()])
    elbow(draw, [fallback.left(), (660, fallback.center()[1]), (660, boxes[1].center()[1]), boxes[1].bottom()])
    note(draw, (1110, 135), "可串联建模插件\n与仿真模块")
    save(image, "llm_sim_flow.png")


def data_flow() -> None:
    image, draw = canvas()
    source = Box(75, 330, 250, 160, "用户输入\n文本、草图、点线集\n与参数表单", "#F6F8FC")
    core = Box(420, 300, 420, 220, "主系统解析\n权限校验、输入规范化、\n任务组织与状态管理", "#EAF1FB")
    plugin = Box(945, 300, 350, 220, "Blender 插件执行\n建模、替换、布局调整\n与结果回传", "#EDF4FF")
    sim = Box(1400, 330, 280, 160, "仿真模块\n生成车辆、人群、船只\n等动态结果", "#EEF8EA")
    project_db = Box(475, 680, 260, 120, "项目库 / 日志库", "#F3F8EC")
    asset_db = Box(980, 680, 280, 120, "资产库 / 场景文件", "#F3F8EC")
    for b in [source, core, plugin, sim, project_db, asset_db]:
        draw_box(draw, b)
    arrow(draw, source.right(), core.left())
    arrow(draw, core.right(), plugin.left())
    arrow(draw, plugin.right(), sim.left())
    arrow(draw, core.bottom(), project_db.top())
    arrow(draw, plugin.bottom(), asset_db.top())
    elbow(draw, [sim.bottom(), (sim.center()[0], 610), asset_db.right()])
    elbow(draw, [asset_db.left(), (890, asset_db.center()[1]), (890, core.center()[1]), core.bottom()])
    note(draw, (1420, 560), "动态结果可进一步\n回写展示层")
    note(draw, (95, 560), "输入先被规范化\n再进入执行链路", fill="#EEF7FF")
    save(image, "data_flow.png")


def function_structure() -> None:
    image, draw = canvas()
    root = Box(650, 95, 500, 110, "智能城市生成系统", "#EAF1FB", text_font=FONT_BOLD)
    row1 = [
        Box(80, 360, 300, 120, "用户与权限管理", "#FFF4EA"),
        Box(470, 360, 300, 120, "插件交互与任务调度", "#FFF4EA"),
        Box(860, 360, 300, 120, "场景生成与资产替换", "#FFF4EA"),
        Box(1250, 360, 300, 120, "布局与生态控制", "#FFF4EA"),
    ]
    row2 = [
        Box(370, 670, 380, 120, "智能交互与多模态解析", "#FFF4EA"),
        Box(1040, 670, 380, 120, "动态仿真与结果展示", "#FFF4EA"),
    ]
    draw_box(draw, root)
    for b in row1 + row2:
        draw_box(draw, b)
        arrow(draw, root.bottom(), b.top())
    note(draw, (88, 150), "治理能力")
    note(draw, (872, 150), "建模与执行能力", fill="#EEF8EA")
    note(draw, (1295, 150), "结果消费能力", fill="#EEF7FF")
    save(image, "function_structure.png")


def draw_lane_header(draw: ImageDraw.ImageDraw, x: int, w: int, text: str, fill: str) -> None:
    draw.rounded_rectangle((x, 90, x + w, 160), radius=20, fill=fill, outline=LINE, width=3)
    bbox = draw.textbbox((0, 0), text, font=FONT_SMALL)
    tx = x + (w - (bbox[2] - bbox[0])) // 2
    ty = 113
    draw.text((tx, ty), text, fill=TEXT, font=FONT_SMALL)
    draw.line((x + w, 80, x + w, HEIGHT - 80), fill="#D8E0EA", width=3)


def draw_circle(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, fill: str, outline: str = LINE, width: int = 4) -> None:
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=fill, outline=outline, width=width)


def draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, w: int, h: int, text: str, fill: str, font: ImageFont.FreeTypeFont = FONT_TINY) -> None:
    pts = [(cx, cy - h // 2), (cx + w // 2, cy), (cx, cy + h // 2), (cx - w // 2, cy)]
    shadow = [(x + 6, y + 6) for x, y in pts]
    draw.polygon(shadow, fill=SHADOW)
    draw.polygon(pts, fill=fill, outline=LINE)
    lines = wrap_text(draw, text, font, w - 22)
    line_h = draw.textbbox((0, 0), "测", font=font)[3] + 6
    total_h = line_h * len(lines)
    y = cy - total_h // 2 - 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = cx - (bbox[2] - bbox[0]) // 2
        draw.text((x, y), line, fill=TEXT, font=font)
        y += line_h


def main_activity_diagram() -> None:
    image, draw = canvas()
    lane_x = [90, 500, 910, 1320]
    lane_w = 300
    headers = [
        ("场景建模师", "#EAF1FB"),
        ("主系统", "#FFF4EA"),
        ("LLM解析模块", "#EEF8EA"),
        ("Blender插件", "#FFF0F0"),
    ]
    for (text, fill), x in zip(headers, lane_x):
        draw_lane_header(draw, x, lane_w, text, fill)
    draw_circle(draw, 240, 205, 18, "#EAF1FB")

    boxes = [
        Box(115, 245, 250, 90, "输入文本、草图\n或参数配置", "#EAF1FB", text_font=FONT_SMALL),
        Box(525, 245, 250, 90, "接收输入并读取\n场景上下文", "#FFF4EA", text_font=FONT_SMALL),
        Box(935, 245, 250, 90, "解析意图并生成\n结构化任务建议", "#EEF8EA", text_font=FONT_SMALL),
        Box(525, 430, 250, 100, "校验资源、场景条件\n和插件能力", "#FFF4EA", text_font=FONT_SMALL),
        Box(115, 620, 250, 95, "查看任务建议并\n确认或补充信息", "#EAF1FB", text_font=FONT_SMALL),
        Box(525, 620, 250, 95, "确认后下发任务\n并登记状态", "#FFF4EA", text_font=FONT_SMALL),
        Box(1345, 620, 250, 95, "执行生成、替换\n或布局调整", "#FFF0F0", text_font=FONT_SMALL),
        Box(525, 835, 250, 95, "保存版本、回写日志\n并刷新结果视图", "#FFF4EA", text_font=FONT_SMALL),
        Box(115, 835, 250, 95, "查看结果预览\n并决定后续处理", "#EAF1FB", text_font=FONT_SMALL),
    ]
    for b in boxes:
        draw_box(draw, b)

    arrow(draw, (240, 223), boxes[0].top())
    arrow(draw, boxes[0].right(), boxes[1].left())
    arrow(draw, boxes[1].right(), boxes[2].left())
    elbow(draw, [boxes[2].bottom(), (boxes[2].center()[0], 390), (1020, 390), (1020, 430)])
    draw_diamond(draw, 1020, 500, 180, 105, "是否满足\n执行条件", "#FFF6E7")
    arrow(draw, (1020, 552), (1020, 620))
    elbow(draw, [(930, 500), (815, 500), boxes[3].right()])
    elbow(draw, [boxes[3].left(), (420, boxes[3].center()[1]), (420, boxes[4].center()[1]), boxes[4].right()])
    arrow(draw, boxes[4].right(), boxes[5].left())
    arrow(draw, boxes[5].right(), boxes[6].left())
    draw_diamond(draw, 1430, 820, 180, 105, "执行是否\n成功", "#FFF6E7")
    elbow(draw, [boxes[6].bottom(), (boxes[6].center()[0], 760), (1430, 760), (1430, 768)])
    elbow(draw, [(1340, 820), (1160, 820), (1160, boxes[7].center()[1]), boxes[7].right()])
    arrow(draw, boxes[7].left(), boxes[8].right())
    note(draw, (1240, 900), "失败时返回错误\n并允许重新提交", fill="#FFF6E7")
    elbow(draw, [(1430, 873), (1430, 950), (1040, 950), (1040, boxes[5].center()[1]), boxes[5].right()])
    draw_diamond(draw, 450, 885, 180, 105, "是否继续\n修改", "#FFF6E7")
    elbow(draw, [boxes[8].right(), (450, boxes[8].center()[1]), (450, 833)])
    elbow(draw, [(360, 885), (85, 885), (85, 480), (115, 480), boxes[0].left()])
    draw_circle(draw, 250, 1000, 18, "#26323F")
    draw_circle(draw, 250, 1000, 10, "#FFFFFF", outline="#26323F", width=3)
    elbow(draw, [(540, 885), (540, 1000), (268, 1000)])
    save(image, "activity_main.png")


def modeler_activity() -> None:
    image, draw = canvas()
    title_box = Box(610, 80, 680, 95, "场景建模师活动图", "#EAF1FB", text_font=FONT_BOLD)
    draw_box(draw, title_box)
    draw_circle(draw, 950, 215, 18, "#EAF1FB")
    boxes = [
        Box(600, 225, 700, 90, "登录并进入建模工作台", "#EAF1FB", text_font=FONT_SMALL),
        Box(130, 395, 430, 110, "选择项目、创建版本\n或加载既有场景", "#EAF1FB", text_font=FONT_SMALL),
        Box(930, 395, 430, 110, "输入文本、草图、点线集\n或参数配置", "#EAF1FB", text_font=FONT_SMALL),
        Box(550, 585, 800, 105, "查看解析后的任务建议\n并确认、补充或调整参数", "#EAF1FB", text_font=FONT_SMALL),
        Box(130, 805, 430, 105, "观察生成结果与动态预览\n判断是否满足建模目标", "#EAF1FB", text_font=FONT_SMALL),
        Box(930, 805, 430, 105, "保存版本、导出场景\n或继续局部修改", "#EAF1FB", text_font=FONT_SMALL),
    ]
    for b in boxes:
        draw_box(draw, b)
    arrow(draw, (950, 233), boxes[0].top())
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (345, 350), (345, boxes[1].top()[1]), boxes[1].top()])
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (1145, 350), (1145, boxes[2].top()[1]), boxes[2].top()])
    elbow(draw, [boxes[1].right(), (600, boxes[1].center()[1]), (600, boxes[3].center()[1]), boxes[3].left()])
    elbow(draw, [boxes[2].left(), (1400, boxes[2].center()[1]), (1400, boxes[3].center()[1]), boxes[3].right()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (345, 740), (345, boxes[4].top()[1]), boxes[4].top()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (1145, 740), (1145, boxes[5].top()[1]), boxes[5].top()])
    draw_diamond(draw, 745, 857, 180, 105, "结果是否\n满足预期", "#FFF6E7")
    elbow(draw, [boxes[4].right(), (655, boxes[4].center()[1]), (655, 857)])
    elbow(draw, [(655, 857), (375, 857)])
    elbow(draw, [(745, 910), (745, 975), (90, 975), (90, 450), boxes[1].left()])
    draw_circle(draw, 1145, 980, 18, "#26323F")
    draw_circle(draw, 1145, 980, 10, "#FFFFFF", outline="#26323F", width=3)
    elbow(draw, [boxes[5].bottom(), (1145, 962)])
    note(draw, (1460, 255), "覆盖输入、确认、\n执行观察与版本处理", fill="#EEF7FF")
    note(draw, (80, 610), "支持多轮试错\n与局部重生成", fill="#FFF6E7")
    save(image, "activity_modeler.png")


def analyst_activity() -> None:
    image, draw = canvas()
    title_box = Box(610, 80, 680, 95, "行业分析师活动图", "#EEF8EA", text_font=FONT_BOLD)
    draw_box(draw, title_box)
    draw_circle(draw, 950, 215, 18, "#EEF8EA")
    boxes = [
        Box(600, 225, 700, 90, "登录并进入分析工作台", "#EEF8EA", text_font=FONT_SMALL),
        Box(130, 395, 430, 110, "选择项目、方案或场景版本\n确定待分析对象", "#EEF8EA", text_font=FONT_SMALL),
        Box(930, 395, 430, 110, "查看静态结果、关键视图\n和相关指标信息", "#EEF8EA", text_font=FONT_SMALL),
        Box(550, 585, 800, 105, "运行或回放仿真结果\n观察车辆、人群、船只等动态差异", "#EEF8EA", text_font=FONT_SMALL),
        Box(130, 805, 430, 105, "比较不同方案并形成\n阶段性分析判断", "#EEF8EA", text_font=FONT_SMALL),
        Box(930, 805, 430, 105, "导出截图、结果文件\n或分析报告", "#EEF8EA", text_font=FONT_SMALL),
    ]
    for b in boxes:
        draw_box(draw, b)
    arrow(draw, (950, 233), boxes[0].top())
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (345, 350), (345, boxes[1].top()[1]), boxes[1].top()])
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (1145, 350), (1145, boxes[2].top()[1]), boxes[2].top()])
    elbow(draw, [boxes[1].right(), (600, boxes[1].center()[1]), (600, boxes[3].center()[1]), boxes[3].left()])
    elbow(draw, [boxes[2].left(), (1400, boxes[2].center()[1]), (1400, boxes[3].center()[1]), boxes[3].right()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (345, 740), (345, boxes[4].top()[1]), boxes[4].top()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (1145, 740), (1145, boxes[5].top()[1]), boxes[5].top()])
    draw_diamond(draw, 745, 857, 180, 105, "是否需要\n继续比较", "#FFF6E7")
    elbow(draw, [boxes[4].right(), (655, boxes[4].center()[1]), (655, 857)])
    elbow(draw, [(655, 857), (375, 857)])
    elbow(draw, [(745, 910), (745, 975), (90, 975), (90, 450), boxes[1].left()])
    draw_circle(draw, 1145, 980, 18, "#26323F")
    draw_circle(draw, 1145, 980, 10, "#FFFFFF", outline="#26323F", width=3)
    elbow(draw, [boxes[5].bottom(), (1145, 962)])
    note(draw, (1460, 255), "以结果消费、仿真观察\n和方案比较为主", fill="#EEF7FF")
    note(draw, (80, 610), "支持多方案循环比较\n与阶段复盘", fill="#FFF6E7")
    save(image, "activity_analyst.png")


def admin_activity() -> None:
    image, draw = canvas()
    title_box = Box(610, 80, 680, 95, "系统管理员活动图", "#FFF1E6", text_font=FONT_BOLD)
    draw_box(draw, title_box)
    draw_circle(draw, 950, 215, 18, "#FFF1E6")
    boxes = [
        Box(600, 225, 700, 90, "登录并进入后台管理工作台", "#FFF1E6", text_font=FONT_SMALL),
        Box(130, 395, 430, 110, "维护用户、角色和权限关系\n调整可见菜单与访问范围", "#FFF1E6", text_font=FONT_SMALL),
        Box(930, 395, 430, 110, "配置插件、模型服务\n和资源库接入状态", "#FFF1E6", text_font=FONT_SMALL),
        Box(550, 585, 800, 105, "监控任务执行状态、查询日志\n并定位权限或服务异常", "#FFF1E6", text_font=FONT_SMALL),
        Box(130, 805, 430, 105, "处理越权、失败任务\n或资源失效问题", "#FFF1E6", text_font=FONT_SMALL),
        Box(930, 805, 430, 105, "保存配置变更并形成\n审计记录", "#FFF1E6", text_font=FONT_SMALL),
    ]
    for b in boxes:
        draw_box(draw, b)
    arrow(draw, (950, 233), boxes[0].top())
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (345, 350), (345, boxes[1].top()[1]), boxes[1].top()])
    elbow(draw, [boxes[0].bottom(), (boxes[0].center()[0], 350), (1145, 350), (1145, boxes[2].top()[1]), boxes[2].top()])
    elbow(draw, [boxes[1].right(), (600, boxes[1].center()[1]), (600, boxes[3].center()[1]), boxes[3].left()])
    elbow(draw, [boxes[2].left(), (1400, boxes[2].center()[1]), (1400, boxes[3].center()[1]), boxes[3].right()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (345, 740), (345, boxes[4].top()[1]), boxes[4].top()])
    elbow(draw, [boxes[3].bottom(), (boxes[3].center()[0], 740), (1145, 740), (1145, boxes[5].top()[1]), boxes[5].top()])
    draw_diamond(draw, 745, 857, 180, 105, "是否存在\n持续异常", "#FFF6E7")
    elbow(draw, [boxes[4].right(), (655, boxes[4].center()[1]), (655, 857)])
    elbow(draw, [(655, 857), (375, 857)])
    elbow(draw, [(745, 910), (745, 975), (90, 975), (90, 450), boxes[1].left()])
    draw_circle(draw, 1145, 980, 18, "#26323F")
    draw_circle(draw, 1145, 980, 10, "#FFFFFF", outline="#26323F", width=3)
    elbow(draw, [boxes[5].bottom(), (1145, 962)])
    note(draw, (1460, 255), "以治理、配置、\n监控与审计追踪为主", fill="#EEF7FF")
    note(draw, (80, 610), "支持反复巡检\n和异常处理闭环", fill="#FFF6E7")
    save(image, "activity_admin.png")


def main() -> None:
    system_overview()
    vertical_flow(
        "modeler_flow.png",
        "#EAF1FB",
        [
            "登录并进入建模工作台",
            "选择项目或创建场景版本",
            "输入文本、草图、点线集\n或参数配置",
            "系统解析任务并联动展示\n关联参数与候选资源",
            "调用 Blender 插件执行生成、替换\n或布局调整任务",
            "预览结果、运行仿真并进行局部修订",
            "保存项目、导出场景并记录过程日志",
        ],
        [(2, "可同时接收\n多模态输入"), (5, "支持反复试错\n与版本对比")],
    )
    vertical_flow(
        "analyst_flow.png",
        "#EEF8EA",
        [
            "登录并进入分析工作台",
            "选择项目、方案或场景版本",
            "查看三维场景结果、截图\n和关键指标信息",
            "运行或回放动态仿真结果\n观察不同方案差异",
            "比较多个方案并形成分析判断",
            "导出图像、结果数据\n或阶段性分析报告",
        ],
        [(2, "关注结果消费\n而非建模过程"), (4, "支持横向对比\n与阶段复盘")],
    )
    vertical_flow(
        "admin_flow.png",
        "#FFF1E6",
        [
            "登录并进入后台管理工作台",
            "维护用户、角色与权限关系",
            "配置插件、模型服务\n和资源库接入信息",
            "监控任务执行状态\n与系统运行异常",
            "查询日志、定位问题\n并处理越权或故障行为",
            "保存配置变更并形成审计记录",
        ],
        [(1, "决定用户可见\n菜单与数据范围"), (4, "支撑持续运行\n与问题追踪")],
    )
    asset_replace_flow()
    layout_ecology_flow()
    llm_sim_flow()
    data_flow()
    function_structure()
    main_activity_diagram()
    modeler_activity()
    analyst_activity()
    admin_activity()


if __name__ == "__main__":
    main()
