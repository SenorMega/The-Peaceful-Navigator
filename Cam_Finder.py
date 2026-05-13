import xml.etree.ElementTree as ET
import re
import os
import math
import requests
import json

# --- Configuration ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# KML file containing the speed and red light cameras from Google My Maps
kml_file_name = 'camera_locations.kml' # Updated to match your current KML file name
kml_file_path = os.path.join(script_dir, kml_file_name)

# Red Light Camera API Endpoint (DataSF SODA API)
red_light_api_url = "https://data.sfgov.org/resource/uzmr-g2uc.json?$select=intersection,point&$limit=5000"

# -------------------

def parse_kml(file_path):
    """Parses a KML file exported from Google My Maps to extract Placemark data."""
    cameras = []
    if not os.path.exists(file_path):
        print(f"Error: KML file not found at '{file_path}'")
        return cameras
        
    try:
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(file_path)
        root = tree.getroot()
        
        for placemark in root.findall('.//kml:Placemark', ns):
            data = {'type': 'speed'} # Defaulting to speed, adjust if needed based on description
            
            name_element = placemark.find('kml:name', ns)
            data['name'] = name_element.text.strip() if name_element is not None and name_element.text else 'Unnamed'
            
            description_element = placemark.find('kml:description', ns)
            if description_element is not None and description_element.text:
                clean_desc = re.sub(r'<.*?>', '', description_element.text).strip()
                data['description'] = clean_desc
            else:
                data['description'] = ''
                
            point = placemark.find('kml:Point', ns)
            if point is not None:
                coordinates_element = point.find('kml:coordinates', ns)
                if coordinates_element is not None and coordinates_element.text:
                    coords_text = coordinates_element.text.strip()
                    try:
                        lon_str, lat_str, *_ = coords_text.split(',')
                        data['longitude'] = float(lon_str)
                        data['latitude'] = float(lat_str)
                        
                        if -180 <= data['longitude'] <= 180 and -90 <= data['latitude'] <= 90:
                            cameras.append(data)
                        else:
                            print(f"Warning: Invalid coordinates ({data['latitude']}, {data['longitude']}) for '{data['name']}'. Skipping.")
                    except (ValueError, IndexError) as e:
                        print(f"Warning: Could not parse coordinates '{coords_text}' for '{data['name']}'. Error: {e}")
            else:
                print(f"Warning: Placemark '{data['name']}' does not contain Point/coordinates.")
                
    except ET.ParseError as e:
        print(f"Error parsing KML file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during KML parsing: {e}")
        
    return cameras

def fetch_red_light_api(api_url):
    """Fetches Red Light Camera citation data from the DataSF API and extracts unique locations."""
    print(f"\nFetching Red Light Camera data from API: {api_url}")
    red_light_cameras = []
    unique_locations = set()

    try:
        response = requests.get(api_url, timeout=30)
        response.raise_for_status()
        api_data = response.json()

        print(f"Received {len(api_data)} records from API.")

        processed_count = 0
        for record in api_data:
            if 'point' in record and isinstance(record['point'], dict) and 'coordinates' in record['point']:
                coords = record['point']['coordinates']
                intersection_name = record.get('intersection', f'Unknown Intersection {processed_count+1}').strip()

                if isinstance(coords, list) and len(coords) == 2:
                    try:
                        longitude = float(coords[0])
                        latitude = float(coords[1])

                        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                            continue
                        if math.isnan(latitude) or math.isnan(longitude):
                            continue

                        location_tuple = (latitude, longitude)

                        if location_tuple not in unique_locations:
                            unique_locations.add(location_tuple)
                            red_light_cameras.append({
                                'name': intersection_name,
                                'latitude': latitude,
                                'longitude': longitude,
                                'type': 'red light'
                            })
                        processed_count += 1
                    except (ValueError, TypeError):
                        pass

        print(f"Found {len(red_light_cameras)} unique red light camera locations from API.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from API: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during API processing: {e}")

    return red_light_cameras

# --- Main execution ---
if __name__ == "__main__":
    print("Starting camera data extraction...")
    
    # Parse Cameras from local KML
    extracted_speed_cameras = parse_kml(kml_file_path)
    if extracted_speed_cameras:
        print(f"Successfully extracted {len(extracted_speed_cameras)} camera locations from local KML.")
    else:
        print("No camera data extracted from local KML.")

    # Fetch Red Light Cameras from DataSF API
    extracted_red_light_cameras = fetch_red_light_api(red_light_api_url)

    # Combine the lists
    all_cameras = extracted_speed_cameras + extracted_red_light_cameras

    if all_cameras:
        print(f"\nTotal unique camera locations ready for export: {len(all_cameras)}")
        
        print("\nSample of combined data (first 3):")
        for i, camera in enumerate(all_cameras[:3]):
            print(f"  {i+1}. Type: {camera.get('type', 'unknown')}, Name: {camera['name']}, Coords: ({camera['latitude']:.6f}, {camera['longitude']:.6f})")

        # Write data to JSON file
        output_json_filename = 'camera_data.json'
        output_json_path = os.path.join(script_dir, output_json_filename)
        
        try:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                json.dump(all_cameras, f, indent=2)
            print(f"\n✅ Successfully wrote {len(all_cameras)} camera locations to {output_json_filename}")
            print(f"You can now push {output_json_filename} to GitHub!")
        except Exception as e:
            print(f"\n❌ Error writing data to {output_json_filename}: {e}")

    else:
        print("\nNo camera data available to write.")