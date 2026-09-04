import re

def parse_dji_srt_file(srt_path: str):
    """
    解析大疆 SRT 文件，返回一个以 frameId 为键的字典
    """
    telemetry_dict = {}
    
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 按空行分割每个字幕块
    blocks = content.strip().split('\n\n')
    
    for block in blocks:
        lines = block.split('\n')
        if len(lines) < 4:
            continue
            
        # 1. 提取帧号 (假设每 33ms 一帧，我们简化为字幕块的索引，或者从 FrameCnt 提取)
        frame_match = re.search(r'FrameCnt:\s*(\d+)', lines[2])
        frame_id = int(frame_match.group(1)) if frame_match else int(lines[0])
        
        # 2. 提取时间戳
        time_match = re.search(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}', lines[2])
        timestamp = time_match.group(0) if time_match else ""
        
        # 3. 提取核心遥测数据 (使用正则表达式)
        data_line = lines[3]
        
        lat = re.search(r'\[latitude:\s*([-\d.]+)\]', data_line)
        lon = re.search(r'\[longitude:\s*([-\d.]+)\]', data_line)
        alt = re.search(r'rel_alt:\s*([-\d.]+)', data_line)
        pitch = re.search(r'gb_pitch:\s*([-\d.]+)', data_line)
        yaw = re.search(r'gb_yaw:\s*([-\d.]+)', data_line)
        roll = re.search(r'gb_roll:\s*([-\d.]+)', data_line)
        
        # 如果经纬度解析成功，则存入字典
        if lat and lon and alt and pitch:
            telemetry_dict[frame_id] = {
                "frameId": frame_id,
                "timestamp": timestamp,
                "latitude": float(lat.group(1)),
                "longitude": float(lon.group(1)),
                "altitude": float(alt.group(1)),
                "pitch": float(pitch.group(1)),
                "yaw": float(yaw.group(1)) if yaw else 0.0,
                "roll": float(roll.group(1)) if roll else 0.0
            }
            
    return telemetry_dict

# 测试代码
if __name__ == "__main__":
    test_line = "[iso: 170] [shutter: 1/3200.0] [fnum: 1.7] [ev: 0] [color_md: default] [ae_meter_md: 1] [focal_len: 24.00] [dzoom_ratio: 1.00], [latitude: 24.832949] [longitude: 102.840047] [rel_alt: 25.126 abs_alt: 1968.195] [gb_yaw: 62.2 gb_pitch: -26.5 gb_roll: 0.0] [dehaze_level: 0] [dehaze_mode: 0]"
    
    pitch = re.search(r'gb_pitch:\s*([-\d.]+)', test_line)
    print(f"提取到的 Pitch: {pitch.group(1)}") # 预期输出: -26.5