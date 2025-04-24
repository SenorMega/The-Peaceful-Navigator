import xml.etree.ElementTree as ET
import re
import os
# import csv # No longer needed for red light cameras
import math
import requests # <--- Import the requests library
import json # For handling potential JSON errors, though requests.json() usually suffices

# --- Configuration ---
script_dir = os.path.dirname(os.path.abspath(__file__))

# Speed Camera KML file
kml_file_name = 'speed_cameras.kml'
kml_file_path = os.path.join(script_dir, kml_file_name)

# Red Light Camera API Endpoint (DataSF SODA API)
# We select only intersection and point columns, limit to 5000 records (adjust if needed)
red_light_api_url = "https://data.sfgov.org/resource/uzmr-g2uc.json?$select=intersection,point&$limit=5000"

# -------------------

# Definition for parse_kml stays exactly the same as before...
def parse_kml(file_path):
    """
    Parses a KML file exported from Google My Maps to extract Placemark data.
    (Keep this function exactly as it was when it worked)
    """
    speed_cameras = []
    if not os.path.exists(file_path):
        print(f"Error: KML file not found at '{file_path}'")
        return speed_cameras
    try:
        ns = {'kml': 'http://www.opengis.net/kml/2.2'}
        tree = ET.parse(file_path)
        root = tree.getroot()
        for placemark in root.findall('.//kml:Placemark', ns):
            data = {'type': 'speed'}
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
                             speed_cameras.append(data)
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
    return speed_cameras


# New function to fetch data from the API
def fetch_red_light_api(api_url):
    """
    Fetches Red Light Camera citation data from the DataSF API and extracts unique locations.

    Args:
        api_url (str): The SODA API endpoint URL.

    Returns:
        list: A list of dictionaries, where each dictionary represents a unique
              red light camera location with 'name', 'longitude', 'latitude', 'type'.
              Returns an empty list if the API request fails or data is malformed.
    """
    print(f"Fetching Red Light Camera data from API: {api_url}")
    red_light_cameras = []
    unique_locations = set() # To track unique lat/lon pairs

    try:
        response = requests.get(api_url, timeout=30) # Add a timeout (in seconds)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response
        api_data = response.json()

        print(f"Received {len(api_data)} records from API.")

        processed_count = 0
        for record in api_data:
            # Check if the 'point' field exists and has 'coordinates'
            if 'point' in record and isinstance(record['point'], dict) and 'coordinates' in record['point']:
                coords = record['point']['coordinates']
                intersection_name = record.get('intersection', f'Unknown Intersection {processed_count+1}').strip()

                # Coordinates in Socrata API are usually [longitude, latitude]
                if isinstance(coords, list) and len(coords) == 2:
                    try:
                        longitude = float(coords[0])
                        latitude = float(coords[1])

                        # Basic validation
                        if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                            # print(f"Warning: Invalid coordinates ({latitude}, {longitude}) found for {intersection_name}. Skipping.")
                            continue
                        
                        # Check if NaN
                        if math.isnan(latitude) or math.isnan(longitude):
                             # print(f"Warning: NaN coordinates found for {intersection_name}. Skipping.")
                             continue

                        location_tuple = (latitude, longitude)

                        # If this location is new, add it
                        if location_tuple not in unique_locations:
                            unique_locations.add(location_tuple)
                            red_light_cameras.append({
                                'name': intersection_name,
                                'latitude': latitude,
                                'longitude': longitude,
                                'type': 'red light'
                            })
                        processed_count += 1

                    except (ValueError, TypeError) as e:
                        # print(f"Warning: Could not parse coordinates '{coords}' for {intersection_name}. Error: {e}")
                        pass # Silently skip malformed coordinates for now
            # else:
                # print(f"Warning: Record missing 'point' or 'coordinates': {record}")


        print(f"Found {len(red_light_cameras)} unique red light camera locations.")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from API: {e}")
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response from API: {e}")
        print(f"Response text: {response.text[:500]}...") # Print beginning of response
    except Exception as e:
        print(f"An unexpected error occurred during API processing: {e}")

    return red_light_cameras


# --- Main execution ---
if __name__ == "__main__":
    # Parse Speed Cameras from KML
    extracted_speed_cameras = parse_kml(kml_file_path)
    if extracted_speed_cameras:
        print(f"Successfully extracted {len(extracted_speed_cameras)} speed camera locations from KML.")
    else:
        print("No speed camera data extracted from KML.")

    # Fetch Red Light Cameras from API
    extracted_red_light_cameras = fetch_red_light_api(red_light_api_url)
    if extracted_red_light_cameras:
         print(f"Successfully extracted {len(extracted_red_light_cameras)} unique red light camera locations from API.")
    else:
         print("No red light camera data extracted from API.")


    # Combine the lists
    all_cameras = extracted_speed_cameras + extracted_red_light_cameras

    if all_cameras:
        print(f"\nTotal unique camera locations found: {len(all_cameras)}")
        # Here you would typically pass 'all_cameras' to your mapping function/module
        # For now, just print a sample
        print("\nSample of combined data (first 5):")
        for i, camera in enumerate(all_cameras[:5]):
             print(f"  {i+1}. Type: {camera['type']}, Name: {camera['name']}, Coords: ({camera['latitude']:.6f}, {camera['longitude']:.6f})")
    else:
        print("\nNo camera data available to display.")


    # ... (Combine the lists into 'all_cameras') ...

    if all_cameras:
        print(f"\nTotal unique camera locations found: {len(all_cameras)}")
        # Here you would typically pass 'all_cameras' to your mapping function/module
        # For now, just print a sample
        print("\nSample of combined data (first 5):")
        for i, camera in enumerate(all_cameras[:5]):
             print(f"  {i+1}. Type: {camera['type']}, Name: {camera['name']}, Coords: ({camera['latitude']:.6f}, {camera['longitude']:.6f})")



        # --- NEW WAY: WRITE PURE JSON DATA TO A .json FILE ---
        output_json_filename = 'camera_data.json' # Note the .json extension
        output_json_path = os.path.join(script_dir, output_json_filename)
        try:
            with open(output_json_path, 'w', encoding='utf-8') as f:
                # Dump only the list/array directly as JSON
                json.dump(all_cameras, f, indent=2)
            print(f"\nSuccessfully wrote {len(all_cameras)} camera locations to {output_json_filename}")
        except Exception as e:
            print(f"\nError writing data to {output_json_filename}: {e}")
        # --- END OF NEW CODE ---
        
         
        # --- WRITE DATA TO A .JS FILE ---
        #output_js_filename = 'camera_data.js'
        #output_js_path = os.path.join(script_dir, output_js_filename)
        # try:
            # Use json.dumps for proper formatting of the list within the JS variable
            # We are creating a JS file that declares a constant variable 'cameraData'
            # js_content = f"const cameraData = {json.dumps(all_cameras, indent=2)};"

            # with open(output_js_path, 'w', encoding='utf-8') as f:
            #     f.write(js_content)
            # print(f"\nSuccessfully wrote {len(all_cameras)} camera locations to {output_js_filename}")

        # except Exception as e:
        #     print(f"\nError writing data to {output_js_filename}: {e}")
        # --- END OF CODE ---*/

    else:
        print("\nNo camera data available to display.")
