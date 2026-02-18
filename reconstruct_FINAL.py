from PIL import Image
import struct

def load_ds_palette(filepath):
    """Load a DS palette file and convert BGR555 to RGB"""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    palette = []
    for i in range(0, len(data), 2):
        color16 = struct.unpack('<H', data[i:i+2])[0]
        
        # BGR555: extract 5-bit components
        r = (color16 & 0x001F)
        g = (color16 & 0x03E0) >> 5
        b = (color16 & 0x7C00) >> 10
        
        # Convert to 8-bit
        r8 = int((r / 31.0) * 255)
        g8 = int((g / 31.0) * 255)
        b8 = int((b / 31.0) * 255)
        
        palette.append((r8, g8, b8))
    
    return palette

def decode_4bpp_tile(tile_bytes):
    """Convert 32 bytes into an 8x8 tile"""
    pixels = []
    for byte in tile_bytes:
        pixel1 = byte & 0x0F
        pixel2 = (byte >> 4) & 0x0F
        pixels.append(pixel1)
        pixels.append(pixel2)
    
    # Arrange into 8x8 grid
    tile = []
    for y in range(8):
        row = []
        for x in range(8):
            row.append(pixels[y * 8 + x])
        tile.append(row)
    
    return tile

def wrap_ds_coordinate(x, y):
    """
    Handle DS coordinate wrapping
    Y is 8-bit (0-255), values >= 192 represent negative positions
    X is 9-bit (0-511), values >= 256 represent negative positions
    """
    # Y wrapping (8-bit: 0-255)
    if y >= 192:
        y = y - 256
    
    # X wrapping (9-bit: 0-511)
    if x >= 256:
        x = x - 512
    
    return x, y

def parse_oam_attrs(attr0, attr1, attr2):
    """
    Parse OAM attributes according to DS documentation
    Returns a dictionary with all parsed fields
    """
    # OBJ Attribute 0
    y_coord = attr0 & 0xFF                      # Bits 0-7
    rot_scaling = (attr0 >> 8) & 0x1            # Bit 8
    
    if rot_scaling:
        double_size = (attr0 >> 9) & 0x1        # Bit 9 (when rotation/scaling on)
        obj_disable = 0
    else:
        double_size = 0
        obj_disable = (attr0 >> 9) & 0x1        # Bit 9 (when rotation/scaling off)
    
    obj_mode = (attr0 >> 10) & 0x3              # Bits 10-11
    mosaic = (attr0 >> 12) & 0x1                # Bit 12
    colors_palettes = (attr0 >> 13) & 0x1       # Bit 13 (0=16/16, 1=256/1)
    obj_shape = (attr0 >> 14) & 0x3             # Bits 14-15
    
    # OBJ Attribute 1
    x_coord = attr1 & 0x1FF                     # Bits 0-8 (9-bit value)
    
    if rot_scaling:
        rot_scaling_param = (attr1 >> 9) & 0x1F # Bits 9-13 (when rotation/scaling on)
        h_flip = 0
        v_flip = 0
    else:
        rot_scaling_param = 0
        h_flip = (attr1 >> 12) & 0x1            # Bit 12 (when rotation/scaling off)
        v_flip = (attr1 >> 13) & 0x1            # Bit 13 (when rotation/scaling off)
    
    obj_size = (attr1 >> 14) & 0x3              # Bits 14-15
    
    # OBJ Attribute 2
    tile_index = attr2 & 0x3FF                   # Bits 0-9 (tile number)
    priority = (attr2 >> 10) & 0x3              # Bits 10-11
    palette_num = (attr2 >> 12) & 0xF           # Bits 12-15
    
    # Size lookup according to DS docs
    SIZE_TABLE = {
        # Shape 0: Square
        0: {0: (8, 8), 1: (16, 16), 2: (32, 32), 3: (64, 64)},
        # Shape 1: Horizontal
        1: {0: (16, 8), 1: (32, 8), 2: (32, 16), 3: (64, 32)},
        # Shape 2: Vertical
        2: {0: (8, 16), 1: (8, 32), 2: (16, 32), 3: (32, 64)},
        # Shape 3: Prohibited
        3: {0: (8, 8), 1: (8, 8), 2: (8, 8), 3: (8, 8)}
    }
    
    width, height = SIZE_TABLE[obj_shape][obj_size]
    
    # Apply coordinate wrapping
    x_coord, y_coord = wrap_ds_coordinate(x_coord, y_coord)
    
    return {
        # Attr0 fields
        'y': y_coord,
        'rot_scaling': rot_scaling,
        'double_size': double_size,
        'obj_disable': obj_disable,
        'obj_mode': obj_mode,
        'mosaic': mosaic,
        'colors_palettes': colors_palettes,  # 0=16/16, 1=256/1
        'shape': obj_shape,
        
        # Attr1 fields
        'x': x_coord,
        'rot_scaling_param': rot_scaling_param,
        'h_flip': h_flip,
        'v_flip': v_flip,
        'size': obj_size,
        
        # Attr2 fields
        'tile_number': tile_index,
        'priority': priority,
        'palette_number': palette_num,
        
        # Calculated
        'width': width,
        'height': height
    }

def render_sprite(tile_data, obj, palette, tile_multiplier=4, show_transparent=False):
    """
    Render a sprite from tiles according to OAM object attributes
    
    tile_multiplier: Multiply tile_number by this to get actual tile index
    show_transparent: If True, render color 0 instead of making it transparent (for debugging)
    """
    TILE_SIZE = 32  # 32 bytes per 8x8 tile in 4bpp
    
    width = obj['width']
    height = obj['height']
    tile_idx = obj['tile_number']
    h_flip = obj['h_flip']
    v_flip = obj['v_flip']
    
    tiles_wide = width // 8
    tiles_tall = height // 8
    
    actual_start_tile = tile_idx * tile_multiplier
    
    # Create image
    if show_transparent:
        # Use white background so we can see everything
        img = Image.new('RGBA', (width, height), (255, 255, 255, 255))
    else:
        img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    tile_num = 0
    for ty in range(tiles_tall):
        for tx in range(tiles_wide):
            current_tile_idx = actual_start_tile + tile_num
            tile_offset = current_tile_idx * TILE_SIZE
            
            if tile_offset + TILE_SIZE > len(tile_data):
                tile_num += 1
                continue
            
            tile_bytes = tile_data[tile_offset:tile_offset + TILE_SIZE]
            tile = decode_4bpp_tile(tile_bytes)
            
            # Calculate tile position on sprite
            tile_x = tx * 8
            tile_y = ty * 8
            
            # Render tile pixels
            for py in range(8):
                for px in range(8):
                    palette_idx = tile[py][px]
                    
                    # CHANGED: Option to show color 0
                    if not show_transparent and palette_idx == 0:
                        continue
                    
                    if palette_idx >= len(palette):
                        continue
                    
                    color = palette[palette_idx]
                    color_rgba = color + (255,)
                    
                    # Calculate pixel position
                    pixel_x = tile_x + px
                    pixel_y = tile_y + py
                    
                    # Apply flips
                    if h_flip:
                        pixel_x = (width - 1) - pixel_x
                    if v_flip:
                        pixel_y = (height - 1) - pixel_y
                    
                    img.putpixel((pixel_x, pixel_y), color_rgba)
            
            tile_num += 1
    
    return img

def parse_custom_oam_format(oam_data):
    """
    Parse the custom OAM format used in face.bin
    
    Structure:
    - 10 byte header
    - Set 1: count specified in header, 6 bytes per object
    - Set 2: 2 byte count + objects at 6 bytes each
    
    Returns: (header_info, set1_objects, set2_objects)
    """
    # Parse header
    header = {
        'total_size': struct.unpack('<H', oam_data[0:2])[0],
        'byte_2_3': struct.unpack('<H', oam_data[2:4])[0],
        'multiplier': struct.unpack('<H', oam_data[4:6])[0], #not entirely sure it is multiplier
        'set2_offset_adjust': struct.unpack('<H', oam_data[6:8])[0],#not entirely confident it is an offset, but it's been consistent. unused
        'set1_count': struct.unpack('<H', oam_data[8:10])[0]
    }
    
    set1_objects = []
    set2_objects = []
    
    # Parse Set 1
    offset = 10
    for i in range(header['set1_count']):
        if offset + 6 > len(oam_data):
            break
        
        attr0 = struct.unpack('<H', oam_data[offset:offset+2])[0]
        attr1 = struct.unpack('<H', oam_data[offset+2:offset+4])[0]
        attr2 = struct.unpack('<H', oam_data[offset+4:offset+6])[0]
        
        obj = parse_oam_attrs(attr0, attr1, attr2)
        obj['set'] = 1
        obj['index'] = i
        set1_objects.append(obj)
        
        offset += 6
    
    # Parse Set 2
    if offset + 2 <= len(oam_data):
        set2_count = struct.unpack('<H', oam_data[offset:offset+2])[0]
        offset += 2
        
        for i in range(set2_count):
            if offset + 6 > len(oam_data):
                break
            
            attr0 = struct.unpack('<H', oam_data[offset:offset+2])[0]
            attr1 = struct.unpack('<H', oam_data[offset+2:offset+4])[0]
            attr2 = struct.unpack('<H', oam_data[offset+4:offset+6])[0]
            
            obj = parse_oam_attrs(attr0, attr1, attr2)
            obj['set'] = 2
            obj['index'] = i
            set2_objects.append(obj)
            
            offset += 6
    
    return header, set1_objects, set2_objects

def reconstruct_portrait(tiles_path, oam_path, palette1_path, palette2_path, 
                        output_path, use_set=1, debug=True, show_transparent=False):
    """
    Reconstruct a portrait in HMDS Given details provided from Parse_Face.py
    
    use_set: 1 or 2 (which set of objects to render)
    show_transparent: If True, render color 0 instead of making it transparent (for debugging)
    """
    # Load data
    with open(tiles_path, 'rb') as f:
        tile_data = f.read()
    
    with open(oam_path, 'rb') as f:
        oam_data = f.read()
    
    palette1 = load_ds_palette(palette1_path)
    palette2 = load_ds_palette(palette2_path)
    palettes = [palette1, palette2]
    
    # Parse OAM
    header, set1_objects, set2_objects = parse_custom_oam_format(oam_data)
    
    if debug:
        print("="*70)
        print("OAM HEADER")
        print("="*70)
        for key, value in header.items():
            print(f"  {key}: {value}")
    
    # Select which set to use
    objects = set1_objects if use_set == 1 else set2_objects
    
    if debug:
        print(f"\n{'='*70}")
        print(f"RENDERING SET {use_set} ({len(objects)} objects)")
        print(f"{'='*70}")
    
    # Find bounds
    min_x = min(obj['x'] for obj in objects)
    max_x = max(obj['x'] + obj['width'] for obj in objects)
    min_y = min(obj['y'] for obj in objects)
    max_y = max(obj['y'] + obj['height'] for obj in objects)
    
    width = max_x - min_x
    height = max_y - min_y
    
    if debug:
        print(f"\nCanvas: {width}x{height}")
        print(f"X: {min_x} to {max_x}")
        print(f"Y: {min_y} to {max_y}\n")
    
    # Create canvas
    canvas = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    # Render each object IN REVERSE ORDER
    # Lower OBJ numbers should appear on top when priority is equal
    for obj in reversed(objects):
        if obj['obj_disable']:
            if debug:
                print(f"  OBJ {obj['index']:2d}: DISABLED (skipping)")
            continue
        
        # Select palette
        pal_idx = obj['palette_number']
        if pal_idx >= len(palettes):
            pal_idx = 0
        palette = palettes[pal_idx]
        
        # Render sprite
        sprite = render_sprite(tile_data, obj, palette, header['multiplier'], show_transparent)
        
        # Paste onto canvas
        paste_x = obj['x'] - min_x
        paste_y = obj['y'] - min_y
        canvas.paste(sprite, (paste_x, paste_y), sprite)
        
        if debug:
            flags = ""
            if obj['h_flip']: flags += "H"
            if obj['v_flip']: flags += "V"
            if obj['rot_scaling']: flags += "R"
            
            print(f"  OBJ {obj['index']:2d}: ({obj['x']:3d},{obj['y']:3d}) "
                  f"{obj['width']:2d}x{obj['height']:2d} "
                  f"tile={obj['tile_number']:3d} pal={obj['palette_number']} "
                  f"{flags if flags else '--'}")
    
    # Save
    canvas.save(output_path)
    if debug:
        print(f"\nSaved: {output_path}")

if __name__ == "__main__":
    import sys
    
    use_set = 2 if len(sys.argv) > 1 and sys.argv[1] == '--set2' else 1
    
    reconstruct_portrait(
        'outputs/characters/00_Claire/binFiles/00_neutral_tiles.bin',
        'outputs/characters/00_Claire/binFiles/00_neutral_oam.bin',
        'outputs/characters/00_Claire/binFiles/palette1.bin',
        'outputs/characters/00_Claire/binFiles/palette2.bin',
        f'claire_clean_set{use_set}.png',
        use_set=use_set,
        debug=True
    )
