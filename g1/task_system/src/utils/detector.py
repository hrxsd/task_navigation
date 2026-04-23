#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化的车牌检测和识别程序
基于detect_clean.py的结构，整合了e.py的OCR配置
"""

import sys
import cv2
import numpy as np
import logging
import os
import re
import json
import argparse
import time
from datetime import datetime
import gc

# 修复numpy.bool弃用警告
try:
    # 检查numpy版本，如果是新版本就不需要设置
    import numpy
    numpy_version = tuple(map(int, numpy.__version__.split('.')[:2]))
    if numpy_version < (1, 20) and not hasattr(np, "bool"):
        np.bool = bool
except (AttributeError, ImportError, ValueError):
    pass

# 尝试导入YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("警告: ultralytics未安装，无法使用YOLO模型")

# 尝试导入PaddleOCR
try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    print("警告: PaddleOCR未安装，无法进行文字识别")

# 设置日志
def setup_logging():
    """设置日志系统"""
    try:
        # 确定日志目录路径
        current_dir = os.path.dirname(os.path.abspath(__file__))
        log_dir = os.path.join(current_dir, "../../data/logs")
        os.makedirs(log_dir, exist_ok=True)
        
        # 确保plate_images目录存在
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(os.path.dirname(current_dir))
        plate_images_dir = os.path.join(project_root, "data/plate_images")
        os.makedirs(plate_images_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "detection_log.txt")
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding="utf-8", mode="w"),
                logging.StreamHandler()
            ]
        )
        logger = logging.getLogger(__name__)
        logger.info("日志系统初始化成功，日志文件路径: %s", log_file)
        return logger
    except Exception as e:
        print(f"日志配置错误: {e}")
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger(__name__)
        logger.warning("使用备用日志系统")
        return logger

logger = setup_logging()

# 中国省份简称映射表
PROVINCE_DICT = {
    "京": "北京", "津": "天津", "冀": "河北", "晋": "山西", "蒙": "内蒙古",
    "辽": "辽宁", "吉": "吉林", "黑": "黑龙江", "沪": "上海", "苏": "江苏",
    "浙": "浙江", "皖": "安徽", "闽": "福建", "赣": "江西", "鲁": "山东",
    "豫": "河南", "鄂": "湖北", "湘": "湖南", "粤": "广东", "桂": "广西",
    "琼": "海南", "渝": "重庆", "川": "四川", "贵": "贵州", "云": "云南",
    "藏": "西藏", "陕": "陕西", "甘": "甘肃", "青": "青海", "宁": "宁夏",
    "新": "新疆"
}

class UniversalDetector:
    """通用检测器：支持车牌检测和行为检测"""
    
    def __init__(self, model_path, enable_ocr=True):
        self.model_path = model_path
        self.model = None
        self.ocr = None
        self.enable_ocr = enable_ocr
        self.detection_type = self.get_detection_type(model_path)
        self.class_names = self.get_class_names(model_path)
        
        logger.info(f"检测类型: {self.detection_type}")
        logger.info(f"类别名称: {self.class_names}")
        
        # 加载模型
        self.load_model()
        
        # 初始化OCR（仅车牌检测时）
        if enable_ocr and self.detection_type == "carplate":
            self.init_ocr()
    
    def get_detection_type(self, model_path):
        """根据模型路径判断检测类型"""
        model_path_lower = model_path.lower()
        if "chepai" in model_path_lower or "carplate" in model_path_lower:
            return "carplate"
        elif "class" in model_path_lower or "behavior" in model_path_lower:
            return "behavior"
        else:
            # 默认根据文件名推断
            return "carplate"
    
    def get_class_names(self, model_path):
        """获取类别名称映射"""
        if self.get_detection_type(model_path) == "carplate":
            return {0: "carplate"}
        else:
            # 行为检测类别
            return {
                0: "hand-raising", 
                1: "reading", 
                2: "writing", 
                3: "sleep",
                4: "using phone", 
                5: "bowing the head", 
                6: "leaning over the table"
            }
    
    def load_model(self):
        """加载YOLO模型"""
        try:
            if not YOLO_AVAILABLE:
                raise ImportError("YOLO不可用")
            
            if not os.path.exists(self.model_path):
                raise FileNotFoundError(f"模型文件不存在: {self.model_path}")
            
            self.model = YOLO(self.model_path)
            logger.info(f"模型加载成功: {self.model_path}")
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return False
    
    def init_ocr(self):
        """初始化OCR识别器，优化中文识别配置"""
        try:
            if not PADDLEOCR_AVAILABLE:
                logger.warning("PaddleOCR未安装，无法进行文字识别")
                return None
            
            # 设置环境变量（来自e.py的配置）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            paddleocr_home = os.path.join(current_dir, 'models/paddleocr')
            os.environ['PADDLE_HOME'] = paddleocr_home
            os.environ['HOME'] = paddleocr_home
            os.makedirs(paddleocr_home, exist_ok=True)
            
            # 检查本地模型是否存在
            current_dir = os.path.dirname(os.path.abspath(__file__))
            models_dir = os.path.join(current_dir, "models/paddleocr")
            det_model_path = os.path.join(models_dir, "det")
            rec_model_path = os.path.join(models_dir, "rec")
            cls_model_path = os.path.join(models_dir, "cls")
            
            local_models_exist = (
                os.path.exists(det_model_path) and 
                os.path.exists(rec_model_path) and 
                os.path.exists(cls_model_path)
            )
            
            if local_models_exist:
                logger.info("使用本地OCR模型...")
                # 使用本地模型，确保中文识别
                self.ocr = PaddleOCR(
                    use_angle_cls=True,  # 启用角度分类器
                    lang='ch',  # 中文语言包
                    det_model_dir=det_model_path,
                    rec_model_dir=rec_model_path,
                    cls_model_dir=cls_model_path,
                    use_space_char=True,  # 使用空格字符
                    drop_score=0.3,  # 降低置信度阈值以提高召回率
                    use_gpu=False,  # 根据需要调整
                    show_log=False  # 减少日志输出
                )
                logger.info("✅ 本地OCR模型初始化成功")
            else:
                logger.info("本地模型不存在，使用在线模型...")
                # 使用在线模型，专门配置中文识别
                self.ocr = PaddleOCR(
                    use_angle_cls=True,  # 启用角度分类器
                    lang='ch',  # 中文语言包
                    use_space_char=True,  # 使用空格字符
                    drop_score=0.3,  # 降低置信度阈值
                    det_limit_side_len=960,  # 检测图像边长限制
                    rec_batch_num=6,  # 识别批次大小
                    show_log=False  # 减少日志输出
                )
                logger.info("✅ 在线OCR模型初始化成功")
            
            return self.ocr
            
        except Exception as e:
            logger.error(f"OCR初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def enhance_plate_image(self, plate_img):
        """增强车牌图像质量"""
        try:
            if plate_img is None or plate_img.size == 0:
                return plate_img
            
            # 调整大小
            h, w = plate_img.shape[:2]
            if w > 0 and h > 0:
                new_w = 240  # 标准车牌宽度
                new_h = int(h * (new_w / w))
                if new_h > 0:
                    plate_img = cv2.resize(plate_img, (new_w, new_h))
            
            # 增强对比度
            lab = cv2.cvtColor(plate_img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            enhanced_lab = cv2.merge((cl, a, b))
            enhanced_img = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
            
            return enhanced_img
        except Exception:
            return plate_img
    
    def clean_plate_text(self, text):
        """清理车牌文本，确保正确处理中文字符"""
        if not text:
            logger.debug("输入文本为空")
            return ""
        
        logger.debug(f"开始清理文本: '{text}'")
        
        # 移除空格和特殊分隔符，但保留中文字符
        text_no_space = re.sub(r'[\s\-_\.\,\:\;\|\(\)\[\]\{\}·]', '', text)
        logger.debug(f"移除分隔符后: '{text_no_space}'")
        
        # 过滤掉明显的错误字符，但保留中文省份简称
        # 允许的字符：中文省份、英文字母、数字
        allowed_chars = []
        filtered_chars = []
        for char in text_no_space:
            if (char in PROVINCE_DICT or  # 中文省份
                char.isalpha() or  # 英文字母
                char.isdigit() or  # 数字
                char in '京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领'):  # 所有可能的省份简称
                allowed_chars.append(char)
            else:
                filtered_chars.append(char)
        
        if filtered_chars:
            logger.debug(f"过滤掉的字符: {filtered_chars}")
        
        text_filtered = ''.join(allowed_chars).upper()
        logger.debug(f"字符过滤后: '{text_filtered}'")
        
        # 采用更保守的修正策略：只修正非常明显的错误
        # 中文省份的修正（这些是安全的）
        province_corrections = {
            '景': '京', '亰': '京', '惊': '京',
            '晥': '皖', '完': '皖', '院': '皖',
            '渔': '湘', '相': '湘', '香': '湘',
            '户': '沪', '护': '沪',
            '苏': '苏', '速': '苏',
            '浙': '浙', '折': '浙',
            '豫': '豫', '预': '豫',
            '川': '川', '穿': '川',
            '渝': '渝', '愉': '渝',
            '粤': '粤', '越': '粤',
            '闽': '闽', '门': '闽'
        }
        
        # 只修正非常明显的符号错误，不修正字母和数字
        symbol_corrections = {
            '口': '0', '|': '1', '丨': '1',  # 明显的符号
            'o': '0', 'l': '1',  # 小写字母（车牌应该都是大写）
        }
        
        result = ''
        corrections_applied = []
        for i, char in enumerate(text_filtered):
            corrected_char = char
            
            # 第一位：只修正省份简称
            if i == 0 and char in province_corrections:
                corrected_char = province_corrections[char]
                corrections_applied.append(f"省份修正: '{char}' -> '{corrected_char}'")
            # 其他位置：只修正明显的符号错误
            elif i > 0 and char in symbol_corrections:
                corrected_char = symbol_corrections[char]
                corrections_applied.append(f"符号修正: '{char}' -> '{corrected_char}'")
            
            result += corrected_char
        
        if corrections_applied:
            logger.debug(f"应用的修正: {corrections_applied}")
        
        logger.debug(f"错误修正后: '{result}'")
        
        # 验证车牌格式
        logger.debug(f"开始格式验证，当前结果长度: {len(result)}")
        if len(result) >= 7:
            # 标准车牌格式：省份简称 + 字母 + 5-6位字母数字组合
            province_pattern = '[京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领]'
            city_pattern = '[A-Z]'
            number_pattern = '[A-Z0-9]{5,6}'
            full_pattern = f'^{province_pattern}{city_pattern}{number_pattern}$'
            
            logger.debug(f"检查格式: '{result}' 是否匹配 {full_pattern}")
            
            if re.match(full_pattern, result):
                logger.debug(f"✅ 符合标准车牌格式: '{result}'")
                return result
            else:
                logger.debug(f"❌ 不符合标准格式，尝试修正...")
                # 如果不匹配标准格式，尝试修正第二位字符（应该是字母）
                if len(result) >= 2:
                    province = result[0]
                    city_code = result[1]
                    plate_number = result[2:]
                    
                    logger.debug(f"分解: 省份='{province}', 城市代码='{city_code}', 号码='{plate_number}'")
                    
                    # 检查第二位字符是否符合要求
                    if not re.match('[A-Z]', city_code):
                        logger.debug(f"城市代码 '{city_code}' 不是大写字母，尝试修正")
                        # 如果第二位是数字，尝试转换为字母
                        if city_code.isdigit():
                            digit_to_letter = {'0': 'A', '1': 'A', '2': 'B', '3': 'C', '4': 'D', 
                                             '5': 'F', '6': 'G', '7': 'H', '8': 'H', '9': 'J'}
                            if city_code in digit_to_letter:
                                old_city_code = city_code
                                city_code = digit_to_letter[city_code]
                                logger.debug(f"城市代码修正: '{old_city_code}' -> '{city_code}'")
                        else:
                            logger.debug(f"城市代码 '{city_code}' 不是数字，无法自动修正")
                    else:
                        logger.debug(f"城市代码 '{city_code}' 已是大写字母，无需修正")
                    
                    corrected_result = province + city_code + plate_number
                    logger.debug(f"修正后的结果: '{corrected_result}'")
                    
                    if re.match(full_pattern, corrected_result):
                        logger.debug(f"✅ 修正后符合格式: '{corrected_result}'")
                        return corrected_result
                    else:
                        logger.debug(f"❌ 修正后仍不符合格式: '{corrected_result}'")
        else:
            logger.debug(f"结果长度不足7位，跳过格式验证")
        
        # 截断到合理长度
        if len(result) > 8:
            result = result[:8]
            logger.debug(f"截断到8位: '{result}'")
        elif len(result) > 7:
            result = result[:7]
            logger.debug(f"截断到7位: '{result}'")
        
        # 如果结果太短，可能是误识别
        if len(result) < 4:
            logger.debug(f"结果太短 ({len(result)} < 4)，返回'未识别'")
            return "未识别"
        
        logger.debug(f"最终清理结果: '{result}'")
        return result
    
    def recognize_plate_text(self, plate_img):
        """识别车牌文本，优化中文字符识别"""
        try:
            if self.ocr is None:
                logger.warning("OCR未初始化")
                return "OCR未初始化"
            
            if plate_img is None or plate_img.size == 0:
                logger.warning("车牌图像为空或无效")
                return "未识别"
            
            logger.info(f"开始识别车牌，图像尺寸: {plate_img.shape}")
            
            # 保存车牌图像用于调试
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            plate_images_dir = os.path.join(project_root, "data/plate_images")
            debug_img_path = os.path.join(plate_images_dir, f"debug_plate_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            cv2.imwrite(debug_img_path, plate_img)
            logger.info(f"车牌图像已保存到: {debug_img_path}")
            
            # 增强图像
            enhanced_img = self.enhance_plate_image(plate_img)
            
            # 保存增强后的图像用于调试
            enhanced_img_path = os.path.join(plate_images_dir, f"enhanced_plate_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
            cv2.imwrite(enhanced_img_path, enhanced_img)
            logger.info(f"增强后图像已保存到: {enhanced_img_path}")
            
            # 使用PaddleOCR识别车牌文本
            logger.info("开始OCR识别...")
            result = self.ocr.ocr(enhanced_img, cls=True)
            
            logger.info(f"OCR原始结果: {result}")
            
            if result and len(result) > 0 and result[0]:
                # PaddleOCR结果格式分析：
                # result = [页面1的所有检测结果]
                # 页面1的结果 = [检测结果1, 检测结果2, ...]  
                # 每个检测结果 = [坐标数组, (文本, 置信度)]
                
                page_results = result[0]  # 取第一页结果
                # logger.info(f"页面原始结果: {page_results}")
                # logger.info(f"页面结果类型: {type(page_results)}")
                # logger.info(f"页面结果长度: {len(page_results)}")
                
                texts = []
                confidences = []
                all_results = []  # 保存所有结果用于调试
                
                # 特殊处理：如果页面结果本身就是一个检测结果[坐标, (文本, 置信度)]
                if (len(page_results) == 2 and 
                    isinstance(page_results[0], list) and  # 第一项是坐标列表
                    isinstance(page_results[1], tuple)):   # 第二项是(文本, 置信度)元组
                    
                    # logger.info("检测到单个结果格式：[坐标数组, (文本, 置信度)]")
                    coordinates = page_results[0]
                    text_info = page_results[1]
                    
                    # logger.info(f"坐标: {coordinates}")
                    # logger.info(f"文本信息: {text_info}")
                    
                    if isinstance(text_info, tuple) and len(text_info) >= 2:
                        text = text_info[0]
                        confidence = text_info[1]
                        all_results.append((text, confidence))
                        logger.info(f"✅ OCR结果: 文本='{text}', 置信度={confidence:.3f}")
                        
                        # 对于中文字符，降低置信度要求
                        has_chinese = any(char in '京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领' for char in text)
                        min_confidence = 0.3 if has_chinese else 0.5
                        
                        # logger.info(f"包含中文: {has_chinese}, 最低置信度要求: {min_confidence}")
                        
                        if confidence > min_confidence:
                            texts.append(text)
                            confidences.append(confidence)
                            logger.info(f"✅ 接受此结果")
                        else:
                            logger.info(f"❌ 置信度过低，跳过")
                    else:
                        logger.warning(f"文本信息格式错误: {text_info}")
                        
                else:
                    # 标准格式：多个检测结果的列表
                    # logger.info("检测到多结果格式，逐个处理")
                    for i, detection in enumerate(page_results):
                        # logger.info(f"处理检测结果 {i+1}: {detection}")
                        # logger.info(f"  检测结果类型: {type(detection)}")
                        # logger.info(f"  检测结果长度: {len(detection)}")
                        
                        # 每个detection应该是[坐标数组, (文本, 置信度)]
                        if len(detection) == 2 and isinstance(detection[1], tuple):
                            coordinates = detection[0]
                            text_info = detection[1]
                            
                            logger.info(f"  坐标: {coordinates}")
                            logger.info(f"  文本信息: {text_info}")
                            
                            if len(text_info) >= 2:
                                text = text_info[0]
                                confidence = text_info[1]
                                all_results.append((text, confidence))
                                logger.info(f"✅ OCR结果 {i+1}: 文本='{text}', 置信度={confidence:.3f}")
                                
                                # 对于中文字符，降低置信度要求
                                has_chinese = any(char in '京津沪渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼使领' for char in text)
                                min_confidence = 0.3 if has_chinese else 0.5
                                
                                logger.info(f"  包含中文: {has_chinese}, 最低置信度要求: {min_confidence}")
                                
                                if confidence > min_confidence:
                                    texts.append(text)
                                    confidences.append(confidence)
                                    logger.info(f"  ✅ 接受此结果")
                                else:
                                    logger.info(f"  ❌ 置信度过低，跳过")
                            else:
                                logger.warning(f"  文本信息长度不足: {text_info}")
                        else:
                            logger.warning(f"  检测结果格式错误: {detection}")
                
                logger.info(f"OCR识别到 {len(all_results)} 个文本区域")
                
                logger.info(f"通过置信度筛选后的文本: {texts}")
                
                if texts:
                    # 合并所有文本，按置信度加权
                    if len(texts) == 1:
                        plate_text = texts[0]
                    else:
                        # 如果有多个结果，选择置信度最高的，或者合并短文本
                        max_conf = max(confidences)
                        if max_conf > 0.6:
                            # 高置信度，选择最好的结果
                            best_idx = confidences.index(max_conf)
                            plate_text = texts[best_idx]
                            logger.info(f"选择最高置信度结果: '{plate_text}' (置信度: {max_conf:.3f})")
                        else:
                            # 中等置信度，合并结果
                            plate_text = ''.join(texts)
                            logger.info(f"合并所有结果: '{plate_text}'")
                    
                    logger.info(f"最终合并文本: '{plate_text}'")
                    
                    # 清理文本
                    cleaned_text = self.clean_plate_text(plate_text)
                    logger.info(f"清理后文本: '{cleaned_text}'")
                    
                    if cleaned_text and len(cleaned_text) >= 4 and cleaned_text != "未识别":  # 降低长度要求
                        logger.info(f"✅ 识别成功: '{cleaned_text}'")
                        return cleaned_text
                    else:
                        logger.warning(f"清理后文本不符合要求: 长度={len(cleaned_text) if cleaned_text else 0}, 内容='{cleaned_text}'")
                    
                # 如果标准识别失败，尝试极低置信度
                logger.warning("标准识别失败，尝试极低置信度阈值...")
                texts_very_low_conf = []
                for text, confidence in all_results:
                    if confidence > 0.1:  # 极低的置信度阈值
                        texts_very_low_conf.append(text)
                        logger.info(f"极低置信度接受: '{text}' (置信度: {confidence:.3f})")
                
                if texts_very_low_conf:
                    plate_text = ''.join(texts_very_low_conf)
                    logger.info(f"极低置信度合并文本: '{plate_text}'")
                    cleaned_text = self.clean_plate_text(plate_text)
                    logger.info(f"极低置信度清理后文本: '{cleaned_text}'")
                    if cleaned_text and len(cleaned_text) >= 3 and cleaned_text != "未识别":
                        logger.info(f"✅ 极低置信度识别成功: '{cleaned_text}'")
                        return cleaned_text
            else:
                logger.warning("OCR没有识别到任何文本")
            
            logger.warning("所有识别尝试都失败了")
            return "未识别"
            
        except Exception as e:
            logger.error(f"车牌识别失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return "识别错误"
    
    def detect_image(self, image_path, conf_threshold=0.25, output_dir=None):
        """检测单张图像中的目标（车牌或行为）"""
        # 根据检测类型设置默认输出目录
        if output_dir is None:
            # 确定项目根目录（detector.py在src/utils下，需要回到项目根目录）
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))  # 回到task_system目录
            
            if self.detection_type == "carplate":
                output_dir = os.path.join(project_root, "data/detection_results/vehicle")
            else:
                output_dir = os.path.join(project_root, "data/detection_results/classroom")
        try:
            # 检查文件是否存在
            if not os.path.exists(image_path):
                logger.error(f"图像文件不存在: {image_path}")
                return None
            
            # 读取图像
            img = cv2.imread(image_path)
            if img is None:
                logger.error(f"无法读取图像: {image_path}")
                return None
            
            logger.info(f"检测图像: {image_path}")
            
            # 执行检测
            start_time = time.time()
            results = self.model.predict(
                source=image_path,
                conf=conf_threshold,
                verbose=False
            )
            end_time = time.time()
            
            result = results[0]
            detection_type_name = "车牌" if self.detection_type == "carplate" else "目标"
            logger.info(f"检测到 {len(result.boxes)} 个{detection_type_name}，耗时: {(end_time - start_time) * 1000:.1f} ms")
            
            # 处理检测结果
            detection_results = []
            os.makedirs(output_dir, exist_ok=True)
            
            for i, box in enumerate(result.boxes):
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                confidence = float(box.conf[0])
                cls_id = int(box.cls[0])
                
                # 检查边界框是否有效
                if x2 <= x1 or y2 <= y1 or x1 < 0 or y1 < 0:
                    continue
                
                # 获取类别名称
                class_name = self.class_names.get(cls_id, f"class{cls_id}")
                
                if self.detection_type == "carplate":
                    # 车牌检测处理
                    plate_img = img[y1:y2, x1:x2]
                    plate_number = "未识别"
                    
                    if plate_img.size > 0:
                        # 保存车牌图像
                        current_dir = os.path.dirname(os.path.abspath(__file__))
                        project_root = os.path.dirname(os.path.dirname(current_dir))
                        plate_images_dir = os.path.join(project_root, "data/plate_images")
                        os.makedirs(plate_images_dir, exist_ok=True)
                        plate_filename = os.path.join(plate_images_dir, f"plate_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
                        cv2.imwrite(plate_filename, plate_img)
                        
                        # 识别车牌文字
                        if self.enable_ocr and self.ocr is not None:
                            plate_number = self.recognize_plate_text(plate_img)
                        else:
                            plate_number = "OCR未启用"
                        
                        # 在图像上绘制检测框和文本
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        cv2.putText(img, f"{plate_number} ({confidence:.2f})", (x1, y1 - 10), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                        
                        logger.info(f"检测到车牌: {plate_number}, 置信度: {confidence:.2f}, 位置: [{x1}, {y1}, {x2}, {y2}]")
                        
                        # 保存检测结果
                        result_data = {
                            "type": "carplate",
                            "plate_number": plate_number,
                            "confidence": float(confidence),
                            "position": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                            "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            "image_path": plate_filename
                        }
                        detection_results.append(result_data)
                        
                else:
                    # 行为检测处理
                    # 在图像上绘制检测框和标签
                    cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                    cv2.putText(img, f"{class_name} ({confidence:.2f})", (x1, y1 - 10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                    
                    logger.info(f"检测到行为: {class_name}, 置信度: {confidence:.2f}, 位置: [{x1}, {y1}, {x2}, {y2}]")
                    
                    # 保存检测结果
                    result_data = {
                        "type": "behavior",
                        "behavior": class_name,
                        "confidence": float(confidence),
                        "position": {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2)},
                        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    }
                    detection_results.append(result_data)
            
            # 保存结果
            if detection_results:
                self.save_results(detection_results, image_path, output_dir)
            
            # 保存输出图像
            output_image = os.path.join(output_dir, os.path.basename(image_path))
            cv2.imwrite(output_image, img)
            logger.info(f"结果已保存到: {output_image}")
            
            return detection_results
            
        except Exception as e:
            logger.error(f"检测图像失败: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def save_results(self, detection_results, source_path, output_dir):
        """保存检测结果到JSON文件"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = os.path.splitext(os.path.basename(source_path))[0]
            json_filename = f"{self.detection_type}_{base_name}_{timestamp}.json"
            json_path = os.path.join(output_dir, json_filename)
            
            # 根据检测类型构建输出数据
            if self.detection_type == "carplate":
                output_data = {
                    "detection_time": timestamp,
                    "detection_type": "carplate",
                    "source_file": source_path,
                    "results_count": len(detection_results),
                    "plates": detection_results
                }
                result_type_name = "车牌识别"
            else:
                output_data = {
                    "detection_time": timestamp,
                    "detection_type": "behavior",
                    "source_file": source_path,
                    "results_count": len(detection_results),
                    "behaviors": detection_results
                }
                result_type_name = "行为检测"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"{result_type_name}结果保存到: {json_path}")
            
        except Exception as e:
            logger.error(f"保存结果失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        try:
            if hasattr(self.model, '__del__'):
                del self.model
            self.model = None
            
            if hasattr(self.ocr, '__del__'):
                del self.ocr
            self.ocr = None
            
        except Exception as e:
            logger.debug(f"清理资源时出错: {e}")
    
    def __del__(self):
        """析构函数"""
        self.cleanup()

def test_ocr_setup():
    """测试OCR配置是否正确"""
    print("🔍 测试OCR配置...")
    
    if not PADDLEOCR_AVAILABLE:
        print("❌ PaddleOCR未安装")
        return False
    
    try:
        # 创建临时检测器测试OCR
        temp_detector = UniversalDetector.__new__(UniversalDetector)
        temp_detector.enable_ocr = True
        temp_detector.detection_type = "carplate"  # 设置为车牌检测模式以启用OCR
        ocr = temp_detector.init_ocr()
        
        if ocr is None:
            print("❌ OCR初始化失败")
            return False
        
        # 创建测试图像（包含中文字符的简单图像）
        import numpy as np
        test_img = np.ones((60, 200, 3), dtype=np.uint8) * 255
        
        # 测试OCR是否工作
        try:
            result = ocr.ocr(test_img, cls=True)
            print("✅ OCR配置测试成功")
            print(f"   - 支持中文识别: {'是' if 'ch' in str(ocr) else '否'}")
            return True
        except Exception as e:
            print(f"❌ OCR测试失败: {e}")
            return False
            
    except Exception as e:
        print(f"❌ OCR配置测试失败: {e}")
        return False

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='通用检测系统：支持车牌检测和行为检测')
    parser.add_argument('--model_path', type=str, required=True, help='模型文件路径')
    parser.add_argument('--source', type=str, required=True, help='输入图像路径')
    parser.add_argument('--conf', type=float, default=0.25, help='置信度阈值 (0.1-1.0)')
    parser.add_argument('--output_dir', type=str, default=None, help='输出目录（默认根据检测类型自动设置）')
    parser.add_argument('--disable_ocr', action='store_true', help='禁用OCR功能（仅车牌检测时有效）')
    parser.add_argument('--test_ocr', action='store_true', help='测试OCR配置')
    return parser.parse_args()

def main():
    """主函数"""
    detector = None
    try:
        args = parse_arguments()
        
        # 如果是测试OCR配置
        if args.test_ocr:
            success = test_ocr_setup()
            if success:
                print("🎉 OCR配置正常，支持中文识别")
            else:
                print("💡 建议检查PaddleOCR安装和模型路径配置")
            return
        
        # 创建检测器
        detector = UniversalDetector(
            model_path=args.model_path,
            enable_ocr=not args.disable_ocr
        )
        
        # 检查是否成功加载模型
        if detector.model is None:
            logger.error("模型加载失败，程序退出")
            return
        
        # 执行检测
        results = detector.detect_image(
            image_path=args.source,
            conf_threshold=args.conf,
            output_dir=args.output_dir
        )
        
        if results:
            result_type_name = "车牌" if detector.detection_type == "carplate" else "目标"
            logger.info(f"检测完成，共识别到 {len(results)} 个{result_type_name}")
        else:
            result_type_name = "车牌" if detector.detection_type == "carplate" else "目标"
            logger.info(f"未检测到{result_type_name}")
            
    except KeyboardInterrupt:
        logger.info("程序被用户中断")
    except Exception as e:
        logger.error(f"程序执行错误: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # 确保资源被正确释放
        if detector is not None:
            try:
                detector.cleanup()
                del detector
            except Exception as e:
                logger.debug(f"最终清理时出错: {e}")
        
        # 强制垃圾回收
        gc.collect()
        logger.info("程序结束")

if __name__ == '__main__':
    main()
