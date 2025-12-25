import datetime
import time
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict
from urllib.parse import urlencode

import requests
from PIL import Image


# ---------- utils ----------
def safe_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[\\/:*?\"<>|]+", "_", s)
    s = re.sub(r"\s+", " ", s)
    return s or "untitled"


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


# ---------- runtime cfg ----------
@dataclass
class RuntimeCfg:
    cookie_str: str
    token: str
    authorization: str
    user_id: str
    tenant_id: str
    start_at: str
    end_at: str

    timeout: int = 60
    retries: int = 3
    sleep_ms: int = 200
    max_workers: int = 8


def cookie_str_to_dict(cookie_str: str) -> dict:
    jar = {}
    for part in (cookie_str or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            jar[k.strip()] = v.strip()
    return jar


def make_session(cfg: RuntimeCfg) -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://video.jw.scut.edu.cn/",
        "Origin": "https://video.jw.scut.edu.cn",
        "X-Requested-With": "XMLHttpRequest",
        "Authorization": cfg.authorization,
        "Accept": "application/json, text/plain, */*",
    })
    s.cookies.update(cookie_str_to_dict(cfg.cookie_str))
    return s


def _get_json_or_raise(r: requests.Response, url: str) -> dict:
    if r.status_code != 200:
        raise RuntimeError(
            f"HTTP {r.status_code}\nURL: {url}\n"
            f"Content-Type: {r.headers.get('Content-Type')}\n"
            f"Body(head 300): {r.text[:300]}"
        )

    ct = (r.headers.get("Content-Type") or "").lower()
    if "application/json" not in ct:
        raise RuntimeError(
            f"Non-JSON response\nURL: {url}\n"
            f"Content-Type: {r.headers.get('Content-Type')}\n"
            f"Body(head 300): {r.text[:300]}"
        )
    return r.json()


# ---------- api: schedules ----------
def fetch_schedules_in_range(cfg: RuntimeCfg, session: requests.Session) -> List[Dict]:
    all_courses: List[Dict] = []
    seen_ids = set()

    start_date = datetime.datetime.strptime(cfg.start_at, "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(cfg.end_at, "%Y-%m-%d").date()

    current_start = start_date
    while current_start <= end_date:
        current_end = min(current_start + datetime.timedelta(days=6), end_date)

        s_str = current_start.strftime("%Y-%m-%d")
        e_str = current_end.strftime("%Y-%m-%d")

        base = "https://video.jw.scut.edu.cn/courseapi/v2/schedule/get-week-schedules"
        qs = {
            "user_id": cfg.user_id,
            "tenant_id": cfg.tenant_id,
            "start_at": s_str,
            "end_at": e_str,
            "token": cfg.token,
        }
        url = f"{base}?{urlencode(qs)}"

        r = session.get(url, timeout=cfg.timeout)
        data = _get_json_or_raise(r, url)

        week_list = data.get("result", {}).get("list", [])
        for day_block in week_list:
            day = day_block.get("day") or ""
            for course in day_block.get("course", []):
                sub_id = str(course.get("id") or "")
                if sub_id and sub_id not in seen_ids:
                    seen_ids.add(sub_id)
                    all_courses.append({
                        "title": course.get("course_title") or "未命名课程",
                        "course_id": str(course.get("course_id") or ""),
                        "sub_id": sub_id,
                        "day": day
                    })

        current_start += datetime.timedelta(days=7)
        time.sleep(0.12)

    all_courses.sort(key=lambda x: x.get("day", ""))
    return all_courses


# ---------- api: ppt urls ----------
def get_ppt_urls(cfg: RuntimeCfg, session: requests.Session, course_id: str, sub_id: str) -> List[str]:
    base = "https://video.jw.scut.edu.cn/pptnote/v1/schedule/search-ppt"
    qs = {"course_id": course_id, "sub_id": sub_id, "page": 1, "per_page": 1000}
    url = f"{base}?{urlencode(qs)}"

    r = session.get(url, timeout=cfg.timeout)
    data = _get_json_or_raise(r, url)

    urls = []
    for item in data.get("list", []):
        try:
            c = item.get("content")
            if not c:
                continue
            obj = json.loads(c)
            u = obj.get("pptimgurl") or obj.get("pptthumb")
            if u:
                urls.append(u)
        except Exception:
            continue

    # 去重保序
    seen = set()
    ordered = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            ordered.append(u)
    return ordered


# ---------- download + merge ----------
def download_one_image(session: requests.Session, url: str, fp: Path, retries: int = 3) -> bool:
    if fp.exists():
        return True

    for _ in range(max(1, retries)):
        try:
            resp = session.get(url, timeout=30, stream=True)
            if resp.status_code == 200:
                ensure_dir(fp.parent)
                with fp.open("wb") as f:
                    for chunk in resp.iter_content(8192):
                        if chunk:
                            f.write(chunk)
                return True
        except Exception:
            time.sleep(0.4)
    return False


def merge_images_to_pdf(image_paths: List[Path], pdf_path: Path) -> int:
    """
    返回：成功合并的图片数量
    """
    valid_imgs = []
    for p in image_paths:
        if not p.exists():
            continue
        try:
            im = Image.open(p)
            if im.mode != "RGB":
                im = im.convert("RGB")
            valid_imgs.append(im)
        except Exception:
            continue

    if not valid_imgs:
        return 0

    ensure_dir(pdf_path.parent)
    valid_imgs[0].save(str(pdf_path), save_all=True, append_images=valid_imgs[1:])
    return len(valid_imgs)

def download_course_to_pdf(
    cfg: RuntimeCfg,
    session: requests.Session,
    course: Dict,
    out_dir: Path,
    keep_images: bool,
    log_fn=None,
    checkpoint_fn=None,
    cancel_cleanup: bool = True
) -> Path:
    """
    下载单节课 PPT 图片并合并为 PDF。
    - checkpoint_fn: 用于暂停/取消检查（每张图前调用）
    - cancel_cleanup: 若取消，清理当前节课目录
    """
    title = safe_name(course.get("title"))
    day = course.get("day") or "unknown_day"
    course_id = str(course.get("course_id") or "")
    sub_id = str(course.get("sub_id") or "")

    course_dir = out_dir / f"{title}_{course_id}"
    occ_dir = course_dir / f"{day}_{sub_id}"
    img_dir = occ_dir / "images"
    pdf_path = occ_dir / f"{day}_{title}.pdf"

    if pdf_path.exists():
        if log_fn:
            log_fn(f"⏭️ 已存在，跳过：{title} [{day}]")
        return pdf_path

    ensure_dir(img_dir)

    try:
        if log_fn:
            log_fn(f"📥 获取 PPT：{title} [{day}] ...")

        urls = get_ppt_urls(cfg, session, course_id, sub_id)
        if not urls:
            raise RuntimeError(f"该节课无 PPT：{title} [{day}]")

        image_paths: List[Path] = []
        for idx, url in enumerate(urls, start=1):
            if checkpoint_fn:
                checkpoint_fn()

            ext = ".jpg" if url.lower().endswith(".jpg") else ".png"
            fp = img_dir / f"{idx:04d}{ext}"
            image_paths.append(fp)

            ok = download_one_image(session, url, fp, retries=cfg.retries)
            if not ok and log_fn:
                log_fn(f"⚠️ 下载失败（跳过该张）：{idx}/{len(urls)}")

            if cfg.sleep_ms > 0:
                time.sleep(cfg.sleep_ms / 1000.0)

        image_paths.sort()
        count = merge_images_to_pdf(image_paths, pdf_path)
        if count <= 0:
            raise RuntimeError(f"合并失败：无有效图片：{title} [{day}]")

        if log_fn:
            log_fn(f"✅ 完成：{title} [{day}]（{count} 张 → PDF）")

        if not keep_images:
            try:
                shutil.rmtree(img_dir, ignore_errors=True)
                if log_fn:
                    log_fn("🧹 已删除原图（images）")
            except Exception:
                pass

        return pdf_path

    except InterruptedError:
        # 取消：清理当前节课目录（半成品）
        if cancel_cleanup:
            try:
                shutil.rmtree(occ_dir, ignore_errors=True)
            except Exception:
                pass
        raise
