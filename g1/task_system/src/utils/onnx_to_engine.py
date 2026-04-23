#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import argparse
import tensorrt as trt
import numpy as np
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description='将 ONNX 模型转换为 TensorRT 引擎')
    parser.add_argument('--onnx_file', type=str, required=True, help='输入的 ONNX 模型文件路径')
    parser.add_argument('--engine_file', type=str, help='输出的 TensorRT 引擎文件路径')
    parser.add_argument('--fp16', action='store_true', help='是否使用 FP16 精度')
    parser.add_argument('--int8', action='store_true', help='是否使用 INT8 精度')
    parser.add_argument('--workspace', type=int, default=8, help='最大工作空间大小(GB)')
    parser.add_argument('--batch_size', type=int, default=1, help='批处理大小')
    parser.add_argument('--verbose', action='store_true', help='是否显示详细日志')
    args = parser.parse_args()
    
    # 如果未指定输出文件，则使用输入文件名替换扩展名
    if args.engine_file is None:
        args.engine_file = args.onnx_file.replace('.onnx', '.engine')
    
    print(f"将 ONNX 模型 {args.onnx_file} 转换为 TensorRT 引擎 {args.engine_file}")
    
    # 创建 TensorRT 日志记录器
    logger = trt.Logger(trt.Logger.VERBOSE if args.verbose else trt.Logger.INFO)
    
    # 创建 TensorRT 构建器
    builder = trt.Builder(logger)
    
    # 创建网络定义
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    
    # 创建 ONNX 解析器
    parser = trt.OnnxParser(network, logger)
    
    # 加载 ONNX 模型
    with open(args.onnx_file, 'rb') as f:
        if not parser.parse(f.read()):
            for error in range(parser.num_errors):
                print(f"ONNX 解析错误: {parser.get_error(error)}")
            return
    
    print("ONNX 模型解析成功")
    
    # 创建构建配置
    config = builder.create_builder_config()
    
    # 设置工作空间大小 - 根据 TensorRT 版本使用不同的 API
    workspace_bytes = args.workspace * (1 << 30)  # 转换为字节
    try:
        # 尝试使用新 API (TensorRT 8.4+)
        config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, workspace_bytes)
        print(f"使用 set_memory_pool_limit 设置工作空间大小: {args.workspace} GB")
    except AttributeError:
        try:
            # 尝试使用旧 API
            config.max_workspace_size = workspace_bytes
            print(f"使用 max_workspace_size 设置工作空间大小: {args.workspace} GB")
        except AttributeError:
            print(f"警告: 无法设置工作空间大小，使用默认值")
    
    # 设置精度
    if args.fp16 and builder.platform_has_fast_fp16:
        print("启用 FP16 精度")
        config.set_flag(trt.BuilderFlag.FP16)
    
    if args.int8 and builder.platform_has_fast_int8:
        print("启用 INT8 精度")
        config.set_flag(trt.BuilderFlag.INT8)
        # 注意: 使用 INT8 需要校准数据，这里简化处理
    
    # 设置批处理大小
    profile = builder.create_optimization_profile()
    input_tensor = network.get_input(0)
    input_shape = input_tensor.shape
    
    # 假设输入是 NCHW 格式
    min_shape = (args.batch_size, input_shape[1], input_shape[2], input_shape[3])
    opt_shape = (args.batch_size, input_shape[1], input_shape[2], input_shape[3])
    max_shape = (args.batch_size, input_shape[1], input_shape[2], input_shape[3])
    
    profile.set_shape(input_tensor.name, min_shape, opt_shape, max_shape)
    config.add_optimization_profile(profile)
    
    # 构建引擎
    print("开始构建 TensorRT 引擎...")
    serialized_engine = builder.build_serialized_network(network, config)
    
    if serialized_engine is None:
        print("构建 TensorRT 引擎失败")
        return
    
    # 保存引擎
    with open(args.engine_file, 'wb') as f:
        f.write(serialized_engine)
    
    print(f"TensorRT 引擎已成功构建并保存到: {args.engine_file}")

if __name__ == '__main__':
    main() 