import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

def load_and_preprocess_data():
    # 加载路径损耗数据（处理编码问题和注释行）
    with open('src/debug/RNX_Cal_DualPol_8.0to40.0GHz_stepNONE_20250720_124420Z.csv', 'rb') as f:
        lines = f.readlines()
    
    # 找到数据开始的行（跳过!开头的注释行）
    data_start = 0
    for i, line in enumerate(lines):
        if not line.startswith(b'!'):
            data_start = i
            break
    
    # 读取数据（指定编码为latin1处理特殊字符）
    path_loss = pd.read_csv(
        'src/debug/RNX_Cal_DualPol_8.0to40.0GHz_stepNONE_20250720_124420Z.csv',
        encoding='latin1',
        skiprows=data_start,
        header=0
    )
    
    # 确保列名正确（处理可能的空格）
    path_loss.columns = [col.strip() for col in path_loss.columns]
    path_loss.columns = ['Frequency', 'Theta', 'Phi']  # 明确指定列名
    
    # 加载标准喇叭天线增益数据
    horn_2_18 = pd.read_csv('src/debug/英联标准增益2-18GHz.csv')
    horn_18_40 = pd.read_csv('src/debug/英联标准增益18-40GHz.csv')
    
    # 统一频率单位为GHz
    horn_2_18['Frequency'] = horn_2_18['freq(MHz)'] / 1000  # MHz转GHz
    horn_18_40['Frequency'] = horn_18_40['FREQ(GHz)']        # 已经是GHz
    
    # 合并两个喇叭数据
    horn_all = pd.concat([
        horn_2_18[['Frequency', 'Gain']],
        horn_18_40[['Frequency', 'gain']].rename(columns={'gain': 'Gain'})
    ]).sort_values('Frequency')
    
    # 验证数据
    print("喇叭增益数据范围验证:")
    print(f"2-18GHz: {horn_2_18['Frequency'].min():.2f}-{horn_2_18['Frequency'].max():.2f} GHz")
    print(f"18-40GHz: {horn_18_40['Frequency'].min():.2f}-{horn_18_40['Frequency'].max():.2f} GHz")
    print(f"合并后: {horn_all['Frequency'].min():.2f}-{horn_all['Frequency'].max():.2f} GHz")
    
    return path_loss, horn_all

def create_interpolator(horn_data):
    """创建插值器，处理边界情况"""
    freqs = horn_data['Frequency'].values
    gains = horn_data['Gain'].values
    
    # 线性插值，超出范围使用最近值
    interpolator = interp1d(
        freqs, gains, 
        kind='linear', 
        bounds_error=False, 
        fill_value=(gains[0], gains[-1]))
    
    return interpolator

def correct_path_loss():
    # 加载并预处理数据
    path_loss, horn_all = load_and_preprocess_data()
    
    # 创建插值器
    gain_interp = create_interpolator(horn_all)
    
    # 计算修正值
    path_loss['Horn_Gain'] = gain_interp(path_loss['Frequency'])
    path_loss['Theta_corrected'] = path_loss['Theta'] - path_loss['Horn_Gain']
    path_loss['Phi_corrected'] = path_loss['Phi'] - path_loss['Horn_Gain']
    
    # 保存结果
    output_file = 'corrected_path_loss_final.csv'
    path_loss.to_csv(output_file, index=False, encoding='utf-8')
    
    print("\n修正结果预览:")
    print(path_loss.head())
    print(f"\n修正完成，结果已保存到 {output_file}")
    
    return path_loss

# 执行修正
if __name__ == '__main__':
    corrected_data = correct_path_loss()
