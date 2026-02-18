import os
from reconstruct_FINAL import reconstruct_portrait

def reconstruct_all_characters(characters_dir, output_dir):
    
    os.makedirs(output_dir, exist_ok=True)
    
    #get all character folders
    
    character_folders = []
    
    for item in os.listdir(characters_dir):
        full_path = os.path.join(characters_dir, item)
        if os.path.isdir(full_path):
            character_folders.append(item)
            
            
    #sort
    character_folders.sort()
    
    print(f"Found {len(character_folders)} characters")
    print("="*80)
    
    #process each
    
    for char_folder in character_folders:
        print(f"Processing: {char_folder}")
        print("-"*80)
        
        bin_dir = os.path.join(characters_dir, char_folder, 'binFiles')
        
        #check if binFiles exists
        
        expression_files = []
        for filename in os.listdir(bin_dir):
            if filename.endswith('_tiles.bin'):
                expression_files.append(filename)
                
        #sort
        expression_files.sort()
        
        print(f"Found {len(expression_files)} expression(s)")
        
        for expr_file in expression_files:
                    # Parse filename: "00_neutral_tiles.bin"
                    expr_name = expr_file.replace('_tiles.bin', '')
                    
                    tiles_path = os.path.join(bin_dir, f'{expr_name}_tiles.bin')
                    oam_path = os.path.join(bin_dir, f'{expr_name}_oam.bin')
                    palette1_path = os.path.join(bin_dir, 'palette1.bin')
                    palette2_path = os.path.join(bin_dir, 'palette2.bin')
                    
                    # Check if OAM file exists
                    if not os.path.exists(oam_path):
                        print(f"    ⚠️  {expr_name}: Missing OAM file, skipping")
                        continue
                    
                    # Create output filename
                    output_filename = f'{char_folder}_{expr_name}.png'
                    output_path = os.path.join(output_dir, output_filename)
                    
                    # Reconstruct!
                    try:
                        reconstruct_portrait(
                            tiles_path,
                            oam_path,
                            palette1_path,
                            palette2_path,
                            output_path
                        )
                        print(f"    ✓ {expr_name}")
                    except Exception as e:
                        print(f"    ✗ {expr_name}: {e}")
                
        print("\n" + "="*80)
        print("Done!")

if __name__ == "__main__":
    reconstruct_all_characters(
        'outputs_cute_petever/characters',      # Where raw extracted characters are
        'reconstructed_portraits_cute_petever'  # Where to save PNG files
    )