def incrementTimeStamp(timestamp_str, seconds_to_add):
    """
    Convert a timestamp string to a datetime, increment it by the specified number of seconds,
    and convert back to the original string format.
    
    Args:
        timestamp_str (str): A string containing a timestamp like "[8/6/24, 2:37:02 AM] James:"
                             or just the timestamp part "8/6/24, 2:37:02 AM"
        seconds_to_add (int): Number of seconds to add to the timestamp
        
    Returns:
        str: The updated timestamp string in the original format
    """
    # Check if the input is a full header or just the timestamp
    if timestamp_str.startswith('[') and ']' in timestamp_str:
        # It's a full header like "[8/6/24, 2:37:02 AM] James:"
        header_pattern = r'^\[([^]]+)\] ([^:]+):'
        match = re.match(header_pattern, timestamp_str)
        
        if not match:
            raise ValueError("Header format not recognized")
        
        # Extract just the timestamp part and the name
        timestamp_part = match.group(1)
        name_part = match.group(2)
    else:
        # It's just the timestamp part
        timestamp_part = timestamp_str
        name_part = None
    
    try:
        # Parse the datetime from the timestamp part (e.g., "8/6/24, 2:37:02 AM")
        dt = datetime.datetime.strptime(timestamp_part, "%m/%d/%y, %I:%M:%S %p")
    except ValueError:
        # Try alternative format if the first one fails
        try:
            dt = datetime.datetime.strptime(timestamp_part, "%m/%d/%Y, %I:%M:%S %p")
        except ValueError as e:
            raise ValueError(f"Could not parse timestamp format: {e}")
    
    # Add the specified number of seconds
    dt = dt + datetime.timedelta(seconds=seconds_to_add)
    
    # Format back to the original format with custom formatting
    # Month and day without leading zeros, hour without leading zero but with AM/PM
    # Minutes and seconds with leading zeros
    try:
        # Use strftime with format codes for removing leading zeros
        # This works on Linux/Mac
        new_timestamp_part = dt.strftime("%-m/%-d/%y, %-I:%M:%S %p")
    except ValueError:
        # Windows doesn't support the dash prefix, so we need a workaround
        month = dt.strftime("%m").lstrip('0')
        day = dt.strftime("%d").lstrip('0')
        year = dt.strftime("%y")
        hour = dt.strftime("%I").lstrip('0')
        minute = dt.strftime("%M")
        second = dt.strftime("%S")
        am_pm = dt.strftime("%p")
        new_timestamp_part = f"{month}/{day}/{year}, {hour}:{minute}:{second} {am_pm}"
    
    # Return in the same format as the input
    if name_part:
        return f"[{new_timestamp_part}] {name_part}:"
    else:
        return new_timestamp_part

def uniquify_chat_headers(chat_content):
    """
    Process WhatsApp chat content to ensure all message headers have unique timestamps.
    
    Args:
        chat_content (str): The raw chat content
        
    Returns:
        str: The processed chat content with unique timestamps
    """
    # The regex pattern to identify WhatsApp message headers AND extract timestamp and name
    # This captures the entire header in group 1, timestamp in group 2, and name in group 3
    header_pattern = r'(^\[([^]]+)\] ([^:]+):)'
    
    # Split into lines
    lines = chat_content.splitlines()
    
    # Track headers and their line numbers
    headers_found = {}  # {header: line_number}
    duplicate_headers = {}  # {header: [line_numbers_of_duplicates]}
    
    # Pre-processing: Strip all LRM characters from the entire file
    for line_num, line in enumerate(lines):
        clean_line = line.replace('\u200e', '')
        lines[line_num] = clean_line
    
    # First pass: identify all headers and duplicates
    for line_num, line in enumerate(lines):
        match = re.search(header_pattern, line)
        if match:
            full_header = match.group(1)
            timestamp = match.group(2)
            sender = match.group(3)
            
            # Create a key that combines timestamp and sender
            key = (timestamp, sender)
            
            if key in headers_found:
                # This is a duplicate header
                if key not in duplicate_headers:
                    # First duplicate found, add the original occurrence to the array
                    duplicate_headers[key] = [headers_found[key]]
                
                # Add this duplicate occurrence
                duplicate_headers[key].append(line_num)
            else:
                # First time seeing this header
                headers_found[key] = line_num
    
    # Print summary of duplicates found
    total_duplicates = sum(len(lines_num) - 1 for lines_num in duplicate_headers.values())
    print(f"Found {len(duplicate_headers)} unique headers with duplicates, totaling {total_duplicates} duplicate instances.")
    
    # Second pass: process and update duplicates
    modified_lines = lines.copy()
    
    for (timestamp, sender), line_numbers in duplicate_headers.items():
        # Original header format from the timestamp and sender
        original_header_format = f"[{timestamp}] {sender}:"
        
        # Process duplicates in order (skip the first occurrence as it stays unchanged)
        for i, line_num in enumerate(line_numbers[1:], 1):
            # Current line contains a duplicate that needs updating
            current_line = modified_lines[line_num]
            
            try:
                # Increment just the timestamp part
                new_timestamp = incrementTimeStamp(timestamp, i)
                
                # Create new header with the incremented timestamp
                new_header = f"[{new_timestamp}] {sender}:"
                
                # Replace just the header part of the line, preserving the rest
                modified_lines[line_num] = current_line.replace(original_header_format, new_header, 1)
            except ValueError as e:
                print(f"Warning: Could not process header on line {line_num + 1}: {e}")
    
    # Join the lines back into a single string
    return '\n'.join(modified_lines)#!/usr/bin/env python3
"""
WhatsApp Chat Archive to HTML Converter

This script converts WhatsApp chat archive zip files into beautifully formatted HTML files.
Usage: python3 whatsapp_to_html.py <zipfile>
"""

import os
import sys
import re
import zipfile
import shutil
import datetime
from html import escape

def validate_zip(zip_path):
    """Validate that the provided file is a valid WhatsApp chat archive zip."""
    if not os.path.exists(zip_path):
        print(f"Error: File '{zip_path}' does not exist.")
        return False
    
    if not zip_path.lower().endswith('.zip'):
        print(f"Error: File '{zip_path}' is not a zip file.")
        return False
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            chat_file_exists = any(file.endswith('_chat.txt') for file in zip_ref.namelist())
            if not chat_file_exists:
                print(f"Error: No '_chat.txt' file found in '{zip_path}'. This doesn't appear to be a valid WhatsApp chat archive.")
                return False
    except zipfile.BadZipFile:
        print(f"Error: '{zip_path}' is not a valid zip file.")
        return False
    
    return True

def parse_chat_line_by_line(chat_content):
    """Parse WhatsApp chat text into structured messages using line-by-line approach."""
    lines = chat_content.splitlines()
    messages = []
    current_message = None
    
    # Pattern to detect if a line starts a new message
    # Looks for [date, time] sender: pattern at start of line
    new_message_pattern = re.compile(r'^\[\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\]\s+.+?:')
    
    # Pattern for system messages without a sender and colon
    system_message_pattern = re.compile(r'^\[\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\]\s+(?!.*?:)')
    
    # Pattern to detect embedded message headers that might appear within content
    embedded_header_pattern = re.compile(r'\[\d{1,2}/\d{1,2}/\d{2,4},\s+\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?\]\s+.+?:')
    
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        line_index += 1
        
        # Skip empty lines
        if not line.strip():
            continue
        
        # Check if line starts a new message
        is_new_message = new_message_pattern.match(line) or system_message_pattern.match(line)
        
        if is_new_message:
            # If we have collected a message, save it
            if current_message:
                messages.append(current_message)
            
            # Start a new message
            current_message = {
                'line_number': line_index,
                'content_lines': [],
                'is_system': False,
                'is_deleted': False,
                'is_edited': False,
                'sender': None,
                'date_str': None,
                'time_str': None,
                'timestamp': None,
                'media': None
            }
            
            # Extract timestamp and sender information
            try:
                # Extract timestamp [DD/MM/YY, HH:MM:SS AM/PM]
                timestamp_match = re.match(r'^\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]', line)
                if timestamp_match:
                    current_message['date_str'] = timestamp_match.group(1)
                    current_message['time_str'] = timestamp_match.group(2)
                    
                    # Parse timestamp
                    current_message['timestamp'] = parse_timestamp(
                        current_message['date_str'], 
                        current_message['time_str'],
                        line_index
                    )
                
                # Get everything after the timestamp bracket
                message_content = line[line.find(']')+1:].strip()
                
                # Determine if it's a system message or a user message
                # User message format: [date, time] Sender: Message content
                # System message format: [date, time] Some system notification
                if ': ' in message_content:
                    # It's a user message
                    sender, content = message_content.split(': ', 1)
                    current_message['sender'] = sender.strip()
                    if content.strip():  # Only add content if not empty
                        current_message['content_lines'].append(content.strip())
                else:
                    # It's a system message
                    current_message['is_system'] = True
                    current_message['sender'] = 'System'
                    current_message['content_lines'].append(message_content)
                    
                    # Check if it's a deleted message
                    if "This message was deleted" in message_content:
                        current_message['is_deleted'] = True
                        # Try to extract who deleted the message
                        if "This message was deleted by" in message_content:
                            deleted_by = message_content.replace("This message was deleted by", "").strip()
                            current_message['sender'] = deleted_by
            
            except Exception as e:
                print(f"Warning: Could not parse message at line {line_index}: {line}")
                print(f"Error: {e}")
                # Still keep a basic version of the message
                if current_message:
                    current_message['content_lines'].append(line.strip())
        
        else:
            # This might be a continuation of the previous message OR it might contain embedded headers
            if current_message:
                # Check if this line contains embedded message headers
                # If so, treat each part as a separate message
                embedded_headers = list(embedded_header_pattern.finditer(line))
                
                if embedded_headers:
                    # Process the line as multiple messages
                    print(f"Line {line_index}: Found {len(embedded_headers)} embedded message headers")
                    
                    # If there's content before the first header, add it to the current message
                    if embedded_headers[0].start() > 0:
                        current_message['content_lines'].append(line[:embedded_headers[0].start()].strip())
                    
                    # Save the current message
                    messages.append(current_message)
                    
                    # Process each embedded header as a new message
                    for i, match in enumerate(embedded_headers):
                        header = match.group(0)
                        
                        # Extract the header part (timestamp and sender)
                        header_match = re.match(r'\[(\d{1,2}/\d{1,2}/\d{2,4}),\s+(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s+(.+?):', header)
                        
                        if header_match:
                            date_str, time_str, sender = header_match.groups()
                            
                            # Create a new message for this header
                            current_message = {
                                'line_number': line_index,
                                'content_lines': [],
                                'is_system': False,
                                'is_deleted': False,
                                'is_edited': False,
                                'sender': sender.strip(),
                                'date_str': date_str,
                                'time_str': time_str,
                                'timestamp': parse_timestamp(date_str, time_str, line_index),
                                'media': None
                            }
                            
                            # Add any content after this header and before the next one
                            content_start = match.end()
                            content_end = embedded_headers[i+1].start() if i+1 < len(embedded_headers) else len(line)
                            if content_start < content_end:
                                content = line[content_start:content_end].strip()
                                if content:
                                    current_message['content_lines'].append(content)
                            
                            # Save this message
                            messages.append(current_message)
                    
                    # Start a fresh message for any subsequent lines
                    current_message = None
                else:
                    # No embedded headers, just a regular continuation line
                    current_message['content_lines'].append(line)
    
    # Don't forget the last message
    if current_message:
        messages.append(current_message)
    
    # Post-processing
    for msg in messages:
        # Join content lines
        content = '\n'.join(msg['content_lines']).strip()
        
        # Check for edited messages
        if " (edited)" in content or " (edited message)" in content:
            msg['is_edited'] = True
            content = content.replace(" (edited)", "").replace(" (edited message)", "")
        
        # Check for media attachments
        media_match = re.search(r'<attached: (.+?)>', content)
        if media_match:
            msg['media'] = media_match.group(1)
            # Remove the media reference from the content
            content = re.sub(r'<attached: .+?>', '', content).strip()
        
        msg['content'] = content
    
    return messages

def parse_timestamp(date_str, time_str, line_number=None):
    """Parse date and time strings into a datetime object."""
    try:
        # Handle various date formats (MM/DD/YY or DD/MM/YY)
        date_parts = date_str.split('/')
        if len(date_parts) != 3:
            print(f"Warning: Invalid date format at line {line_number}: {date_str}")
            return None
            
        # Try to handle both date formats sensibly
        # Assume first number under 13 is month, otherwise it's day
        # This isn't perfect but works for most cases
        month = int(date_parts[0])
        day = int(date_parts[1])
        
        # If month is larger than 12, swap day and month
        if month > 12:
            month, day = day, month
        
        # Handle both 2-digit and 4-digit year formats
        year = int(date_parts[2])
        if year < 100:  # 2-digit year
            year += 2000  # Assume 21st century
        
        # Handle both 12-hour and 24-hour time formats with Unicode space handling
        is_12h_format = 'AM' in time_str or 'PM' in time_str
        
        # Clean up any Unicode spaces and non-breaking spaces
        clean_time_str = time_str
        for space_char in ['\u202f', '\u00a0', '\u2007', '\u2002', '\u2003', '\u2009']:
            clean_time_str = clean_time_str.replace(space_char, ' ')
        
        if is_12h_format:
            # 12-hour format (with AM/PM)
            # Handle AM/PM with various spacing
            am_pm = 'AM' if 'AM' in clean_time_str else 'PM'
            clean_time = clean_time_str.replace(' AM', '').replace('AM', '').replace(' PM', '').replace('PM', '').strip()
            
            time_parts = clean_time.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
            # Adjust hour for PM
            if am_pm == 'PM' and hour < 12:
                hour += 12
            if am_pm == 'AM' and hour == 12:
                hour = 0
        else:
            # 24-hour format
            time_parts = clean_time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1])
            second = int(time_parts[2]) if len(time_parts) > 2 else 0
        
        return datetime.datetime(year, month, day, hour, minute, second)
    
    except (ValueError, IndexError) as e:
        prefix = f"Line {line_number}: " if line_number else ""
        print(f"Warning: {prefix}Could not parse date/time: {date_str}, {time_str}")
        print(f"Error: {e}")
        # For debugging, show the exact character codes in the string
        if 'invalid literal for int()' in str(e):
            print(f"Debug - Time string character codes: {[ord(c) for c in time_str]}")
        return None

def extract_media_files(zip_path, output_dir):
    """Extract all media files from the zip to the media directory."""
    media_dir = os.path.join(output_dir, 'media')
    os.makedirs(media_dir, exist_ok=True)
    
    media_files = []
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        total_files = len([f for f in file_list if not f.endswith('/') and not f.endswith('_chat.txt')])
        
        print(f"Found {total_files} potential media files in the zip archive")
        
        for i, file in enumerate(file_list, 1):
            # Skip _chat.txt and directories
            if file.endswith('/') or file.endswith('_chat.txt'):
                continue
                
            # Show progress for large archives
            if i % 20 == 0 or i == total_files:
                print(f"Processing media file {i}/{total_files}: {os.path.basename(file)}")
            
            # Extract media file
            try:
                zip_ref.extract(file, media_dir)
                
                # Move file to media directory if it's in a subdirectory
                source_path = os.path.join(media_dir, file)
                target_path = os.path.join(media_dir, os.path.basename(file))
                
                if source_path != target_path:
                    # Create parent directory if it doesn't exist
                    os.makedirs(os.path.dirname(target_path), exist_ok=True)
                    try:
                        shutil.move(source_path, target_path)
                    except shutil.Error as e:
                        print(f"Warning: Could not move {source_path} to {target_path}: {e}")
                        # If file already exists, keep original filename structure
                        alt_target = os.path.join(media_dir, file.replace('/', '_'))
                        try:
                            shutil.move(source_path, alt_target)
                            print(f"Moved to alternative path: {alt_target}")
                            media_files.append(file.replace('/', '_'))
                        except Exception as e2:
                            print(f"Error: Failed with alternative path too: {e2}")
                    else:
                        # Clean up empty directories
                        dir_path = os.path.dirname(source_path)
                        try:
                            while dir_path != media_dir:
                                if os.path.exists(dir_path) and not os.listdir(dir_path):
                                    os.rmdir(dir_path)
                                dir_path = os.path.dirname(dir_path)
                        except OSError:
                            pass  # Ignore errors when removing directories
                        
                        media_files.append(os.path.basename(file))
                else:
                    media_files.append(os.path.basename(file))
                
            except Exception as e:
                print(f"Warning: Could not extract file {file}: {e}")
    
    print(f"Successfully extracted {len(media_files)} media files to {media_dir}")
    
    # Print some statistics about media types
    extensions = {}
    for file in media_files:
        ext = os.path.splitext(file)[1].lower()
        extensions[ext] = extensions.get(ext, 0) + 1
    
    print("Media files by type:")
    for ext, count in sorted(extensions.items(), key=lambda x: x[1], reverse=True):
        print(f"  - {ext}: {count} files")
    
    return media_files

def format_markdown(text):
    """Format WhatsApp markdown to HTML."""
    if not text:
        return ""
    
    # First split the text by newlines
    paragraphs = text.split('\n')
    
    # Process each paragraph for markdown formatting
    formatted_paragraphs = []
    for paragraph in paragraphs:
        if paragraph.strip() == "":
            # Keep empty paragraphs to preserve spacing
            formatted_paragraphs.append("&nbsp;")
            continue
            
        # Bold: *text*
        paragraph = re.sub(r'\*(.*?)\*', r'<strong>\1</strong>', paragraph)
        
        # Italic: _text_
        paragraph = re.sub(r'_(.*?)_', r'<em>\1</em>', paragraph)
        
        # Strikethrough: ~text~
        paragraph = re.sub(r'~(.*?)~', r'<del>\1</del>', paragraph)
        
        # Monospace: ```text```
        paragraph = re.sub(r'```(.*?)```', r'<code>\1</code>', paragraph)
        
        # Handle URLs
        url_pattern = r'(https?://[^\s]+)'
        paragraph = re.sub(url_pattern, r'<a href="\1" target="_blank">\1</a>', paragraph)
        
        formatted_paragraphs.append(paragraph)
    
    # Join all paragraphs with line breaks and spacing
    result = '<p>' + '</p><p>'.join(formatted_paragraphs) + '</p>'
    
    # Clean up any consecutive empty paragraphs
    result = re.sub(r'<p>&nbsp;</p>\s*<p>&nbsp;</p>', r'<p>&nbsp;</p>', result)
    
    return result

def generate_html(messages, media_files, output_file):
    """Generate HTML file from parsed messages and media files."""
    # Set of unique senders for the selector
    senders = set(msg['sender'] for msg in messages if not msg.get('is_system', False))
    senders_list = sorted(list(senders))
    
    # Map media files to timestamps when possible
    media_map = {}
    unmatched_count = 0
    
    print("Analyzing media files for timestamp matching...")
    for file in media_files:
        # Try to extract date from filename (e.g., IMG-20250329-WA0001.jpg)
        date_match = re.search(r'(\d{8})', file)
        if date_match:
            date_str = date_match.group(1)
            try:
                # Convert YYYYMMDD to a date object
                file_date = datetime.datetime.strptime(date_str, '%Y%m%d').date()
                if file_date not in media_map:
                    media_map[file_date] = []
                media_map[file_date].append(file)
                print(f"Mapped media file {file} to date {file_date}")
            except ValueError:
                # If date parsing fails, add to unmatched count
                unmatched_count += 1
        else:
            # No date in filename
            unmatched_count += 1
    
    matched_count = sum(len(files) for files in media_map.values())
    print(f"Media mapping results: {matched_count} files mapped to dates, {unmatched_count} files without clear date mapping")
    
    # Track which media files have been used in the conversation
    used_media = set()
    
    # HTML content
    html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WhatsApp Chat</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            background-color: #f0f0f0;
            display: flex;
            min-height: 100vh;
        }
        
        .main-content {
            flex: 1;
            padding: 20px;
            max-width: 800px;
            margin: 0 auto;
            transition: margin 0.3s ease;
        }
        
        .controls-wrapper {
            position: fixed;
            top: 0;
            bottom: 0;
            width: 250px;
            z-index: 100;
            transition: transform 0.3s ease;
        }
        
        .controls-wrapper.left {
            left: 0;
        }
        
        .controls-wrapper.right {
            right: 0;
        }
        
        .controls-wrapper.minimized {
            transform: translateX(calc(100% * var(--direction, -1)));
        }
        
        .controls-wrapper.left.minimized {
            --direction: -1;
        }
        
        .controls-wrapper.right.minimized {
            --direction: 1;
        }
        
        .controls {
            background-color: white;
            padding: 15px;
            box-shadow: 0 1px 5px rgba(0, 0, 0, 0.2);
            height: 100%;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }
        
        .controls-wrapper.left .controls {
            border-right: 1px solid #ddd;
            border-top-right-radius: 10px;
            border-bottom-right-radius: 10px;
        }
        
        .controls-wrapper.right .controls {
            border-left: 1px solid #ddd;
            border-top-left-radius: 10px;
            border-bottom-left-radius: 10px;
        }
        
        .controls select {
            padding: 8px;
            border-radius: 5px;
            border: 1px solid #ccc;
            font-size: 16px;
            width: 100%;
        }
        
        .controls label {
            display: block;
            margin-bottom: 8px;
            font-weight: bold;
        }
        
        .toggle-button {
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            background-color: white;
            border: 1px solid #ddd;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            font-size: 20px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.2);
        }
        
        .controls-wrapper.left .toggle-button {
            right: -20px;
        }
        
        .controls-wrapper.right .toggle-button {
            left: -20px;
        }
        
        .dock-position {
            margin-top: 20px;
        }
        
        .dock-position-label {
            font-weight: bold;
            margin-bottom: 8px;
        }
        
        .dock-buttons {
            display: flex;
            gap: 10px;
        }
        
        .dock-button {
            flex: 1;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 5px;
            background-color: #f5f5f5;
            cursor: pointer;
            text-align: center;
        }
        
        .dock-button.active {
            background-color: #4CAF50;
            color: white;
            border-color: #4CAF50;
        }
        
        .about-section {
            margin-top: 20px;
        }
        
        .about-button {
            width: 100%;
            padding: 8px 12px;
            background-color: #128C7E; /* WhatsApp green */
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        
        .about-button:hover {
            background-color: #075E54; /* Darker WhatsApp green */
        }
        
        .about-modal .about-modal-content {
            background-color: #fefefe;
            margin: 5% auto;
            padding: 20px;
            border: 1px solid #888;
            width: 80%;
            max-width: 700px;
            max-height: 80vh;
            overflow-y: auto;
            border-radius: 10px;
            position: relative;
        }
        
        .about-content {
            line-height: 1.5;
        }
        
        .about-content h3 {
            margin-top: 20px;
            margin-bottom: 10px;
            color: #128C7E;
        }
        
        .about-content ul {
            margin-bottom: 15px;
        }
        
        .about-content li {
            margin-bottom: 8px;
        }
        
        /* Toggle Switches */
        .visibility-controls {
            margin-top: 20px;
            border-top: 1px solid #eee;
            padding-top: 15px;
        }
        
        .visibility-controls h3 {
            margin-bottom: 15px;
            font-size: 16px;
        }
        
        /* Date Filter Controls */
        .date-filter-controls {
            margin-top: 20px;
            border-top: 1px solid #eee;
            padding-top: 15px;
        }
        
        .date-filter-controls h3 {
            margin-bottom: 15px;
            font-size: 16px;
        }
        
        .date-range {
            margin-bottom: 12px;
            display: flex;
            flex-direction: column;
        }
        
        .date-range label {
            margin-bottom: 5px;
            font-weight: bold;
        }
        
        .date-range input[type="date"] {
            padding: 8px;
            border-radius: 5px;
            border: 1px solid #ccc;
            font-size: 14px;
            width: 100%;
        }
        
        .filter-buttons {
            display: flex;
            gap: 8px;
            margin-top: 15px;
        }
        
        .filter-button {
            flex: 1;
            padding: 8px 0;
            border-radius: 5px;
            font-weight: bold;
            cursor: pointer;
            border: none;
            font-size: 14px;
            transition: background-color 0.2s;
        }
        
        .filter-button.apply {
            background-color: #128C7E;
            color: white;
        }
        
        .filter-button.apply:hover {
            background-color: #075E54;
        }
        
        .filter-button.clear {
            background-color: #f1f1f1;
            color: #333;
            border: 1px solid #ddd;
        }
        
        .filter-button.clear:hover {
            background-color: #e1e1e1;
        }
        
        .message.date-filtered {
            display: none;
        }
        
        .date-divider.date-filtered {
            display: none;
        }
        
        .toggle-option {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        
        .switch {
            position: relative;
            display: inline-block;
            width: 46px;
            height: 24px;
        }
        
        .switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: #ccc;
            transition: .4s;
        }
        
        .slider:before {
            position: absolute;
            content: "";
            height: 18px;
            width: 18px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: .4s;
        }
        
        input:checked + .slider {
            background-color: #128C7E;
        }
        
        input:focus + .slider {
            box-shadow: 0 0 1px #128C7E;
        }
        
        input:checked + .slider:before {
            transform: translateX(22px);
        }
        
        .slider.round {
            border-radius: 24px;
        }
        
        .slider.round:before {
            border-radius: 50%;
        }
        
        /* Hidden elements */
        .message.dialog-hidden:not(.has-media) {
            display: none;
        }
        
        .message.media-hidden:not(.has-dialog) {
            display: none;
        }
        
        .chat-container {
            display: flex;
            flex-direction: column;
            gap: 10px;
        }
        
        .message {
            max-width: 75%;
            padding: 10px 15px;
            border-radius: 15px;
            position: relative;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            word-wrap: break-word;
        }
        
        .message .content {
            word-wrap: break-word;
        }
        
        .message .content p {
            margin: 0 0 16px 0;
            min-height: 1em;
        }
        
        .message .content p:last-child {
            margin-bottom: 0;
        }
        
        .sent {
            align-self: flex-end;
            background-color: #DCF8C6;
            margin-right: 10px;
            border-bottom-right-radius: 5px;
        }
        
        .received {
            align-self: flex-start;
            background-color: #FFFFFF;
            border: 1px solid #E5E5EA;
            margin-left: 10px;
            border-bottom-left-radius: 5px;
        }
        
        .system-message {
            align-self: center;
            background-color: #f8f8f8;
            color: #999;
            font-size: 0.9em;
            border: 1px solid #E5E5EA;
            border-radius: 15px;
            max-width: 80%;
            text-align: center;
        }
        
        .deleted-message {
            font-style: italic;
            color: #999;
        }
        
        .edited-label {
            font-size: 0.75em;
            color: #999;
            margin-top: 4px;
            font-style: italic;
        }
        
        .timestamp {
            font-size: 0.75em;
            color: #8E8E93;
            margin-bottom: 3px;
        }
        
        .message-id {
            font-size: 0.75em;
            color: #8E8E93;
            margin-bottom: 2px;
            font-family: monospace;
        }
        
        .media-id {
            font-size: 0.7em;
            color: #8E8E93;
            margin-bottom: 2px;
            font-family: monospace;
            font-style: italic;
        }
        
        .sender {
            font-weight: bold;
            margin-bottom: 5px;
        }
        
        .media-container {
            margin-top: 10px;
            max-width: 100%;
        }
        
        .media-container img {
            max-width: 100%;
            border-radius: 5px;
            cursor: pointer;
        }
        
        .media-container video {
            max-width: 100%;
            border-radius: 5px;
        }
        
        .date-divider {
            text-align: center;
            margin: 20px 0;
            position: relative;
        }
        
        .date-divider::before {
            content: '';
            position: absolute;
            left: 0;
            top: 50%;
            width: 40%;
            height: 1px;
            background-color: #E5E5EA;
        }
        
        .date-divider::after {
            content: '';
            position: absolute;
            right: 0;
            top: 50%;
            width: 40%;
            height: 1px;
            background-color: #E5E5EA;
        }
        
        .date-divider span {
            background-color: #f0f0f0;
            padding: 0 10px;
            position: relative;
            z-index: 1;
            font-size: 0.9em;
            color: #8E8E93;
        }
        
        /* Modal for larger image view */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            overflow: auto;
            background-color: rgba(0,0,0,0.9);
        }
        
        .modal-content {
            margin: auto;
            display: block;
            max-width: 90%;
            max-height: 90%;
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
        }
        
        .close {
            position: absolute;
            top: 15px;
            right: 35px;
            color: #f1f1f1;
            font-size: 40px;
            font-weight: bold;
            cursor: pointer;
        }
        
        /* Responsive adjustments */
        @media screen and (max-width: 768px) {
            .main-content {
                padding: 10px;
            }
            
            .message {
                max-width: 85%;
            }
            
            .controls-wrapper {
                width: 80%;
                max-width: 300px;
            }
            
            .controls-wrapper.minimized {
                transform: translateX(calc(100% * var(--direction, -1)));
            }
            
            body.controls-open {
                overflow: hidden;
            }
        }
        
        code {
            font-family: monospace;
            background-color: #f5f5f5;
            padding: 2px 4px;
            border-radius: 3px;
        }
    </style>
</head>
<body>
    <div id="controls-wrapper" class="controls-wrapper left">
        <div class="controls">
            <h2>Chat Controls</h2>
            <div>
                <label for="self-selector">Select who you are (messages will appear on the right in green):</label>
                <select id="self-selector">
                    <!-- Options will be populated by JavaScript -->
                </select>
            </div>
            <div class="dock-position">
                <div class="dock-position-label">Dock Position:</div>
                <div class="dock-buttons">
                    <div id="dock-left" class="dock-button active">Left</div>
                    <div id="dock-right" class="dock-button">Right</div>
                </div>
            </div>
            <div class="about-section">
                <button id="about-button" class="about-button">About WhatsApp Export</button>
            </div>
            <div class="visibility-controls">
                <h3>Display Options</h3>
                <div class="toggle-option">
                    <label for="toggle-dialog">Show Dialog</label>
                    <label class="switch">
                        <input type="checkbox" id="toggle-dialog" checked>
                        <span class="slider round"></span>
                    </label>
                </div>
                <div class="toggle-option">
                    <label for="toggle-media">Show Media</label>
                    <label class="switch">
                        <input type="checkbox" id="toggle-media" checked>
                        <span class="slider round"></span>
                    </label>
                </div>
            </div>
            <div class="date-filter-controls">
                <h3>Date Filter</h3>
                <div class="date-range">
                    <label for="date-from">From:</label>
                    <input type="date" id="date-from">
                </div>
                <div class="date-range">
                    <label for="date-to">To:</label>
                    <input type="date" id="date-to">
                </div>
                <div class="filter-buttons">
                    <button id="apply-date-filter" class="filter-button apply">Apply Filter</button>
                    <button id="clear-date-filter" class="filter-button clear">Clear Filter</button>
                </div>
            </div>
        </div>
        <div id="toggle-button" class="toggle-button">↓</div>
    </div>
    <div class="main-content">
        <div class="chat-container">
"""

    # Track the current date for adding date dividers
    current_date = None
    
    # Assign message IDs
    for i, msg in enumerate(messages, 1):
        msg['message_id'] = f"{i:08d}"  # Format with leading zeros (8 digits)
    
    for msg in messages:
        message_date = msg['timestamp'].date() if msg['timestamp'] else None
        
        # Add date divider if the date has changed
        if message_date and message_date != current_date:
            formatted_date = message_date.strftime('%A, %B %d, %Y')
            html += f"""
        <div class="date-divider">
            <span>{formatted_date}</span>
        </div>
"""
            current_date = message_date
        
        # Format timestamp
        timestamp = f"{msg['date_str']}, {msg['time_str']}" if msg['date_str'] and msg['time_str'] else "Unknown time"
        
        # Determine message class based on type
        if msg.get('is_system', False):
            message_class = "system-message"
        else:
            # Initial class (will be updated by JavaScript)
            message_class = "received"
            
        # Apply deleted message class if needed
        if msg.get('is_deleted', False):
            message_class += " deleted-message"
        
        # Start message div
        html += f"""
        <div class="message {message_class}">
            <div class="message-id">Message: {msg['message_id']}</div>
"""
        # Add media filename if present
        if msg['media']:
            html += f"""            <div class="media-id">Media: {msg['media']}</div>
"""

        html += f"""            <div class="timestamp">{timestamp}</div>
"""
        
        # Only add sender for non-system messages
        if not msg.get('is_system', False):
            html += f"""            <div class="sender">{escape(msg['sender'] or 'Unknown')}</div>
"""
        
        # Format content based on type
        if msg.get('is_deleted', False):
            html += f"""            <div class="content">This message was deleted</div>
"""
        else:
            # Apply markdown formatting to content
            formatted_content = format_markdown(msg['content'])
            html += f"""            <div class="content">{formatted_content}</div>
"""
            
        # Add edited label if needed
        if msg.get('is_edited', False):
            html += """            <div class="edited-label">Edited</div>
"""
        
        # Add media if attached in the message
        if msg['media']:
            file_extension = os.path.splitext(msg['media'])[1].lower()
            media_path = f"media/{msg['media']}"
            
            if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                html += f"""
            <div class="media-container">
                <img src="{media_path}" alt="Media: {msg['media']}" onclick="openModal(this.src)">
            </div>
"""
            elif file_extension in ['.mp4', '.mov', '.avi', '.3gp']:
                html += f"""
            <div class="media-container">
                <video controls>
                    <source src="{media_path}" type="video/{file_extension[1:]}">
                    Your browser does not support the video tag.
                </video>
            </div>
"""
            else:
                html += f"""
            <div class="media-container">
                <a href="{media_path}" target="_blank">View attached file: {escape(msg['media'])}</a>
            </div>
"""
            # Mark this media as used
            used_media.add(msg['media'])
        
        # Look for potential media files by date
        if message_date and message_date in media_map:
            # Find media files from this date that haven't been assigned yet
            # This is a simple heuristic and might not always match correctly
            for media_file in media_map[message_date][:]:  # Create a copy of the list for safe iteration
                if media_file not in used_media:  # Only use media that hasn't been used yet
                    file_extension = os.path.splitext(media_file)[1].lower()
                    media_path = f"media/{media_file}"
                    
                    if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                        html += f"""
            <div class="media-container">
                <img src="{media_path}" alt="Media: {media_file}" onclick="openModal(this.src)">
            </div>
"""
                    elif file_extension in ['.mp4', '.mov', '.avi', '.3gp']:
                        html += f"""
            <div class="media-container">
                <video controls>
                    <source src="{media_path}" type="video/{file_extension[1:]}">
                    Your browser does not support the video tag.
                </video>
            </div>
"""
                    
                    # Mark this media as used
                    used_media.add(media_file)
                    # Remove this media file from the map to avoid duplicates
                    media_map[message_date].remove(media_file)
                    
                    # Only assign one media file per message unless the message already has one from its content
                    if not msg['media']:
                        break
        
        # Close message div
        html += """
        </div>
"""
    
        # After processing all messages, gather truly unused media files
    unused_media = []
    for file in media_files:
        if file not in used_media:
            unused_media.append(file)
    
    if unused_media:
        print(f"Found {len(unused_media)} unused media files that will be displayed in the 'Additional Media' section")
        html += """
        <div class="date-divider">
            <span>Additional Media</span>
        </div>
"""
        
        for i, media_file in enumerate(unused_media, 1):
            # Generate a special message ID for unused media
            media_msg_id = f"UNUSED-{i:04d}"
            
            file_extension = os.path.splitext(media_file)[1].lower()
            media_path = f"media/{media_file}"
            
            html += f"""
        <div class="message received">
            <div class="message-id">Message: {media_msg_id}</div>
            <div class="media-id">Media: {media_file}</div>
            <div class="timestamp">Unused Media</div>
"""
            
            if file_extension in ['.jpg', '.jpeg', '.png', '.gif']:
                html += f"""
            <div class="media-container">
                <img src="{media_path}" alt="Media: {media_file}" onclick="openModal(this.src)">
            </div>
"""
            elif file_extension in ['.mp4', '.mov', '.avi', '.3gp']:
                html += f"""
            <div class="media-container">
                <video controls>
                    <source src="{media_path}" type="video/{file_extension[1:]}">
                    Your browser does not support the video tag.
                </video>
            </div>
"""
            else:
                html += f"""
            <div class="media-container">
                <a href="{media_path}" target="_blank">View file: {escape(media_file)}</a>
            </div>
"""
            
            html += """
        </div>
"""
    
    # Close main container and add JavaScript for modal functionality
    html += """
    </div>
    </div>
    
    <!-- Image modal -->
    <div id="imageModal" class="modal">
        <span class="close" onclick="closeModal()">&times;</span>
        <img class="modal-content" id="modalImg">
    </div>
    
    <!-- About modal -->
    <div id="aboutModal" class="modal about-modal">
        <div class="about-modal-content">
            <span class="close" onclick="closeAboutModal()">&times;</span>
            <h2>About WhatsApp Chat Export</h2>
            <div class="about-content">
                <p>This viewer displays a WhatsApp chat that was exported using the "Export Chat" feature in WhatsApp. While it preserves most of the conversation, there are some important limitations to be aware of:</p>
                
                <h3>Limitations of WhatsApp Chat Exports</h3>
                <ul>
                    <li><strong>Message Replies:</strong> The export does not preserve reply context. When someone replies to a specific message, that connection is lost in the export.</li>
                    <li><strong>Reactions:</strong> Emoji reactions to messages are not included in the export.</li>
                    <li><strong>Media Quality:</strong> Images and videos may be compressed or reduced in quality.</li>
                    <li><strong>Formatting:</strong> Some advanced formatting might not be preserved exactly as it appeared in WhatsApp.</li>
                    <li><strong>Polls and Interactive Content:</strong> Polls, location sharing, and other interactive content may not export completely.</li>
                </ul>
                
                <h3>What Is Preserved</h3>
                <ul>
                    <li>Text messages with timestamps</li>
                    <li>Basic formatting (bold, italic, strikethrough)</li>
                    <li>Media files (photos, videos, documents, etc.)</li>
                    <li>System messages (when someone joined or left)</li>
                    <li>Information about deleted messages</li>
                </ul>
                
                <p>Due to these limitations, some context in conversations may be lost. This viewer attempts to present the exported chat in the most readable format possible, but cannot restore information that wasn't included in the export.</p>
            </div>
        </div>
    </div>
    
    <script>
        // Populate sender selector and set up message display
        document.addEventListener('DOMContentLoaded', function() {
            // Get all unique senders
            const senders = [];
            const messages = document.querySelectorAll('.message:not(.system-message)');
            
            messages.forEach(message => {
                const senderElement = message.querySelector('.sender');
                if (senderElement) {
                    const sender = senderElement.textContent;
                    if (!senders.includes(sender)) {
                        senders.push(sender);
                    }
                }
            });
            
            // Populate selector
            const selector = document.getElementById('self-selector');
            senders.sort().forEach(sender => {
                const option = document.createElement('option');
                option.value = sender;
                option.textContent = sender;
                selector.appendChild(option);
            });
            
            // Function to update message display based on selected sender
            function updateMessageDisplay() {
                const selectedSender = selector.value;
                
                messages.forEach(message => {
                    const senderElement = message.querySelector('.sender');
                    if (senderElement) {
                        const sender = senderElement.textContent;
                        
                        // Reset classes
                        message.classList.remove('sent', 'received');
                        
                        // Apply correct class
                        if (sender === selectedSender) {
                            message.classList.add('sent');
                        } else {
                            message.classList.add('received');
                        }
                    }
                });
                
                // Save selection to localStorage
                localStorage.setItem('whatsapp-self-sender', selectedSender);
            }
            
            // Set initial selection (try to restore from localStorage)
            const savedSender = localStorage.getItem('whatsapp-self-sender');
            if (savedSender && senders.includes(savedSender)) {
                selector.value = savedSender;
            }
            
            // Update display initially and on change
            updateMessageDisplay();
            selector.addEventListener('change', updateMessageDisplay);
            
            // Controls panel functionality
            const controlsWrapper = document.getElementById('controls-wrapper');
            const toggleButton = document.getElementById('toggle-button');
            const dockLeft = document.getElementById('dock-left');
            const dockRight = document.getElementById('dock-right');
            
            // Set initial state based on localStorage
            function initializeControlPanel() {
                const isMinimized = localStorage.getItem('whatsapp-controls-minimized') === 'true';
                const dockPosition = localStorage.getItem('whatsapp-controls-position') || 'left';
                
                // Set minimized state
                if (isMinimized) {
                    controlsWrapper.classList.add('minimized');
                    toggleButton.textContent = '→';
                } else {
                    toggleButton.textContent = '←';
                }
                
                // Set dock position
                if (dockPosition === 'right') {
                    controlsWrapper.classList.remove('left');
                    controlsWrapper.classList.add('right');
                    dockLeft.classList.remove('active');
                    dockRight.classList.add('active');
                    toggleButton.textContent = isMinimized ? '←' : '→';
                } else {
                    controlsWrapper.classList.add('left');
                    controlsWrapper.classList.remove('right');
                    dockLeft.classList.add('active');
                    dockRight.classList.remove('active');
                    toggleButton.textContent = isMinimized ? '→' : '←';
                }
            }
            
            // Toggle controls visibility
            toggleButton.addEventListener('click', function() {
                const isMinimized = controlsWrapper.classList.toggle('minimized');
                localStorage.setItem('whatsapp-controls-minimized', isMinimized);
                
                const isRight = controlsWrapper.classList.contains('right');
                
                // Update toggle button based on position and state
                if (isMinimized) {
                    toggleButton.textContent = isRight ? '←' : '→';
                } else {
                    toggleButton.textContent = isRight ? '→' : '←';
                }
            });
            
            // Handle dock position change
            dockLeft.addEventListener('click', function() {
                controlsWrapper.classList.remove('right');
                controlsWrapper.classList.add('left');
                dockLeft.classList.add('active');
                dockRight.classList.remove('active');
                
                const isMinimized = controlsWrapper.classList.contains('minimized');
                toggleButton.textContent = isMinimized ? '→' : '←';
                
                localStorage.setItem('whatsapp-controls-position', 'left');
            });
            
            dockRight.addEventListener('click', function() {
                controlsWrapper.classList.remove('left');
                controlsWrapper.classList.add('right');
                dockLeft.classList.remove('active');
                dockRight.classList.add('active');
                
                const isMinimized = controlsWrapper.classList.contains('minimized');
                toggleButton.textContent = isMinimized ? '←' : '→';
                
                localStorage.setItem('whatsapp-controls-position', 'right');
            });
            
            // Initialize control panel state
            initializeControlPanel();
            
            // Set up visibility toggles
            const toggleDialog = document.getElementById('toggle-dialog');
            const toggleMedia = document.getElementById('toggle-media');
            
            // Function to get the current top visible message
            function getTopVisibleMessage() {
                const messages = document.querySelectorAll('.message');
                const scrollTop = window.scrollY || document.documentElement.scrollTop;
                
                for (const message of messages) {
                    // Skip hidden messages
                    if (message.classList.contains('dialog-hidden') && message.classList.contains('media-hidden')) {
                        continue;
                    }
                    
                    // Skip dialog-only messages that are hidden
                    if (message.classList.contains('has-dialog') && !message.classList.contains('has-media') && 
                        message.classList.contains('dialog-hidden')) {
                        continue;
                    }
                    
                    // Skip media-only messages that are hidden
                    if (message.classList.contains('has-media') && !message.classList.contains('has-dialog') && 
                        message.classList.contains('media-hidden')) {
                        continue;
                    }
                    
                    const rect = message.getBoundingClientRect();
                    // Check if the message is fully visible or at least partially visible from the top
                    if (rect.top >= 0 || (rect.top < 0 && rect.bottom > 0)) {
                        return {
                            element: message,
                            topOffset: rect.top
                        };
                    }
                }
                return null;
            }
            
            // Function to restore scroll position to keep the same message visible
            function restoreScrollPosition(referenceMessage) {
                if (referenceMessage && referenceMessage.element) {
                    const newRect = referenceMessage.element.getBoundingClientRect();
                    const scrollAdjustment = newRect.top - referenceMessage.topOffset;
                    
                    // Apply the scroll adjustment
                    window.scrollBy(0, scrollAdjustment);
                }
            }
            
            // Flag messages with dialog and media
            function flagMessagesWithContent() {
                const messages = document.querySelectorAll('.message');
                
                messages.forEach(message => {
                    // Check if message has dialog content
                    const content = message.querySelector('.content');
                    if (content && content.textContent.trim() !== '') {
                        message.classList.add('has-dialog');
                    }
                    
                    // Check if message has media content
                    const media = message.querySelector('.media-container');
                    if (media) {
                        message.classList.add('has-media');
                    }
                });
            }
            
            // Run this once on page load
            flagMessagesWithContent();
            
            // Handle dialog toggle
            toggleDialog.addEventListener('change', function() {
                // Get reference message before making changes
                const referenceMessage = getTopVisibleMessage();
                
                // Toggle dialog visibility
                const messages = document.querySelectorAll('.message.has-dialog');
                messages.forEach(message => {
                    if (this.checked) {
                        message.classList.remove('dialog-hidden');
                    } else {
                        message.classList.add('dialog-hidden');
                    }
                });
                
                // Save state to localStorage
                localStorage.setItem('whatsapp-dialog-visible', this.checked);
                
                // Restore scroll position after a small delay to allow rendering
                setTimeout(() => restoreScrollPosition(referenceMessage), 10);
            });
            
            // Handle media toggle
            toggleMedia.addEventListener('change', function() {
                // Get reference message before making changes
                const referenceMessage = getTopVisibleMessage();
                
                // Toggle media visibility
                const messages = document.querySelectorAll('.message.has-media');
                messages.forEach(message => {
                    if (this.checked) {
                        message.classList.remove('media-hidden');
                    } else {
                        message.classList.add('media-hidden');
                    }
                });
                
                // Save state to localStorage
                localStorage.setItem('whatsapp-media-visible', this.checked);
                
                // Restore scroll position after a small delay to allow rendering
                setTimeout(() => restoreScrollPosition(referenceMessage), 10);
            });
            
            // Initialize visibility toggles from localStorage
            function initializeVisibilityToggles() {
                // Dialog visibility
                const dialogVisible = localStorage.getItem('whatsapp-dialog-visible');
                if (dialogVisible === 'false') {
                    toggleDialog.checked = false;
                    document.querySelectorAll('.message.has-dialog').forEach(message => {
                        message.classList.add('dialog-hidden');
                    });
                }
                
                // Media visibility
                const mediaVisible = localStorage.getItem('whatsapp-media-visible');
                if (mediaVisible === 'false') {
                    toggleMedia.checked = false;
                    document.querySelectorAll('.message.has-media').forEach(message => {
                        message.classList.add('media-hidden');
                    });
                }
            }
            
            // Initialize visibility states
            initializeVisibilityToggles();
            
            // Date filtering functionality
            const dateFromInput = document.getElementById('date-from');
            const dateToInput = document.getElementById('date-to');
            const applyDateFilterBtn = document.getElementById('apply-date-filter');
            const clearDateFilterBtn = document.getElementById('clear-date-filter');
            
            // Find earliest and latest dates in the chat
            function findDateRange() {
                const dateDividers = document.querySelectorAll('.date-divider span');
                let earliestDate = null;
                let latestDate = null;
                
                dateDividers.forEach(divider => {
                    const dateStr = divider.textContent.trim();
                    const date = new Date(dateStr);
                    
                    if (!isNaN(date.getTime())) {
                        if (!earliestDate || date < earliestDate) {
                            earliestDate = date;
                        }
                        if (!latestDate || date > latestDate) {
                            latestDate = date;
                        }
                    }
                });
                
                return { earliestDate, latestDate };
            }
            
            // Format date as YYYY-MM-DD for input field
            function formatDateForInput(date) {
                if (!date) return '';
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            }
            
            // Set initial date range limits
            function initializeDateFilters() {
                const { earliestDate, latestDate } = findDateRange();
                
                if (earliestDate && latestDate) {
                    // Set min/max attributes
                    const earliestStr = formatDateForInput(earliestDate);
                    const latestStr = formatDateForInput(latestDate);
                    
                    dateFromInput.min = earliestStr;
                    dateFromInput.max = latestStr;
                    dateToInput.min = earliestStr;
                    dateToInput.max = latestStr;
                    
                    // Set from/to values from localStorage if they exist
                    const savedFromDate = localStorage.getItem('whatsapp-date-from');
                    const savedToDate = localStorage.getItem('whatsapp-date-to');
                    
                    if (savedFromDate) {
                        dateFromInput.value = savedFromDate;
                    }
                    
                    if (savedToDate) {
                        dateToInput.value = savedToDate;
                    }
                    
                    // Apply filter if values were saved
                    if (savedFromDate || savedToDate) {
                        applyDateFilter();
                    }
                }
            }
            
            // Apply date filter
            function applyDateFilter() {
                // Get reference message before making changes
                const referenceMessage = getTopVisibleMessage();
                
                const fromValue = dateFromInput.value;
                const toValue = dateToInput.value;
                
                // Reset all filters if no dates are selected
                if (!fromValue && !toValue) {
                    clearDateFilter();
                    return;
                }
                
                // First, remove any existing date-filtered class
                document.querySelectorAll('.date-filtered').forEach(el => {
                    el.classList.remove('date-filtered');
                });
                
                // For the end date, always add one day to make it inclusive
                let adjustedToDate = null;
                if (toValue) {
                    const parts = toValue.split('-');
                    // Create a new Date with an extra day
                    const year = parseInt(parts[0]);
                    const month = parseInt(parts[1]) - 1; // JavaScript months are 0-indexed
                    const day = parseInt(parts[2]) + 1; // Add one day
                    adjustedToDate = new Date(year, month, day);
                }
                
                const fromDate = fromValue ? new Date(fromValue) : null;
                
                // Process date dividers
                document.querySelectorAll('.date-divider').forEach(divider => {
                    const dateSpan = divider.querySelector('span');
                    const dateText = dateSpan.textContent.trim();
                    const dividerDate = new Date(dateText);
                    
                    let isVisible = true;
                    
                    // Hide if before start date
                    if (fromDate && dividerDate < fromDate) {
                        isVisible = false;
                    }
                    
                    // Hide if on or after adjusted end date (which is already +1 day)
                    if (adjustedToDate && dividerDate >= adjustedToDate) {
                        isVisible = false;
                    }
                    
                    if (!isVisible) {
                        divider.classList.add('date-filtered');
                    }
                });
                
                // Now apply filtering to messages based on their date dividers
                let currentDateDivider = null;
                
                // Process elements in DOM order
                const allElements = document.querySelectorAll('.date-divider, .message');
                
                for (const element of allElements) {
                    if (element.classList.contains('date-divider')) {
                        // Update current date divider reference
                        currentDateDivider = element;
                    } else if (element.classList.contains('message')) {
                        // If there's a current date divider and it's filtered, filter this message too
                        if (currentDateDivider && currentDateDivider.classList.contains('date-filtered')) {
                            element.classList.add('date-filtered');
                        }
                    }
                }
                
                // Save filter state to localStorage
                localStorage.setItem('whatsapp-date-from', fromValue);
                localStorage.setItem('whatsapp-date-to', toValue);
                
                // Restore scroll position after a small delay
                setTimeout(() => restoreScrollPosition(referenceMessage), 10);
            }
            
            // Clear date filter
            function clearDateFilter() {
                // Get reference message before making changes
                const referenceMessage = getTopVisibleMessage();
                
                // Clear input values
                dateFromInput.value = '';
                dateToInput.value = '';
                
                // Remove filtered class from all elements
                document.querySelectorAll('.date-filtered').forEach(el => {
                    el.classList.remove('date-filtered');
                });
                
                // Clear localStorage
                localStorage.removeItem('whatsapp-date-from');
                localStorage.removeItem('whatsapp-date-to');
                
                // Restore scroll position after a small delay
                setTimeout(() => restoreScrollPosition(referenceMessage), 10);
            }
            
            // Event listeners for date filter controls
            applyDateFilterBtn.addEventListener('click', applyDateFilter);
            clearDateFilterBtn.addEventListener('click', clearDateFilter);
            
            // Update the getTopVisibleMessage function to account for date filtering
            function getTopVisibleMessage() {
                const messages = document.querySelectorAll('.message');
                
                for (const message of messages) {
                    // Skip hidden messages (content filters)
                    if (message.classList.contains('dialog-hidden') && message.classList.contains('media-hidden')) {
                        continue;
                    }
                    
                    // Skip dialog-only messages that are hidden
                    if (message.classList.contains('has-dialog') && !message.classList.contains('has-media') && 
                        message.classList.contains('dialog-hidden')) {
                        continue;
                    }
                    
                    // Skip media-only messages that are hidden
                    if (message.classList.contains('has-media') && !message.classList.contains('has-dialog') && 
                        message.classList.contains('media-hidden')) {
                        continue;
                    }
                    
                    // Skip date-filtered messages
                    if (message.classList.contains('date-filtered')) {
                        continue;
                    }
                    
                    const rect = message.getBoundingClientRect();
                    // Check if the message is fully visible or at least partially visible from the top
                    if (rect.top >= 0 || (rect.top < 0 && rect.bottom > 0)) {
                        return {
                            element: message,
                            topOffset: rect.top
                        };
                    }
                }
                return null;
            }
            
            // Initialize date filters
            initializeDateFilters();
        });
        
        // Image modal functionality
        function openModal(src) {
            document.getElementById('imageModal').style.display = 'block';
            document.getElementById('modalImg').src = src;
        }
        
        function closeModal() {
            document.getElementById('imageModal').style.display = 'none';
        }
        
        // About modal functionality
        const aboutButton = document.getElementById('about-button');
        const aboutModal = document.getElementById('aboutModal');
        
        aboutButton.addEventListener('click', function() {
            aboutModal.style.display = 'block';
        });
        
        function closeAboutModal() {
            aboutModal.style.display = 'none';
        }
        
        // Close modals on Escape key
        document.addEventListener('keydown', function(event) {
            if (event.key === 'Escape') {
                closeModal();
                closeAboutModal();
            }
        });
        
        // Close modals when clicking outside the content
        window.addEventListener('click', function(event) {
            if (event.target === aboutModal) {
                closeAboutModal();
            }
            if (event.target === document.getElementById('imageModal')) {
                closeModal();
            }
        });
    </script>
</body>
</html>
"""
    
    # Write HTML to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

def main():
    """Main function to process WhatsApp chat archive."""
    if len(sys.argv) != 2:
        print("Usage: python3 whatsapp_to_html.py <zipfile>")
        sys.exit(1)
    
    zip_path = sys.argv[1]
    
    # Validate input
    if not validate_zip(zip_path):
        sys.exit(1)
    
    # Create output directory
    base_name = os.path.splitext(os.path.basename(zip_path))[0]
    output_dir = os.path.join(os.path.dirname(os.path.abspath(zip_path)), base_name)
    
    # If directory exists, remove it
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Processing WhatsApp chat archive: {zip_path}")
    
    # Extract and process chat file
    chat_content = ""
    chat_filename = ""
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file in zip_ref.namelist():
            if file.endswith('_chat.txt'):
                chat_filename = file
                try:
                    chat_content = zip_ref.read(file).decode('utf-8')
                    print(f"Found chat file: {file}")
                    break
                except UnicodeDecodeError:
                    # Try with a different encoding
                    try:
                        chat_content = zip_ref.read(file).decode('latin-1')
                        print(f"Decoded chat file with latin-1 encoding: {file}")
                        break
                    except Exception as e:
                        print(f"Error: Could not decode chat file: {file}")
                        print(f"Error details: {e}")
    
    if not chat_content:
        print("Error: Could not find or read _chat.txt in the zip file.")
        sys.exit(1)
        
    print(f"Successfully loaded chat file: {chat_filename} ({len(chat_content)} characters, {len(chat_content.splitlines())} lines)")

    # Preprocess chat content to ensure unique timestamps
    print("Preprocessing chat content to ensure unique timestamps...")
    uniquified_chat_content = uniquify_chat_headers(chat_content)
    
    # Save the uniquified chat file for debugging
    uniquified_chat_path = os.path.join(output_dir, 'uniquified_chat.txt')
    try:
        with open(uniquified_chat_path, 'w', encoding='utf-8') as f:
            f.write(uniquified_chat_content)
        print(f"Saved preprocessed chat file to: {uniquified_chat_path}")
    except Exception as e:
        print(f"Warning: Could not save preprocessed chat file: {e}")

    # Parse the uniquified chat content
    try:
        messages = parse_chat_line_by_line(uniquified_chat_content)
        if not messages:
            print("Error: No messages found in the chat file.")
            sys.exit(1)
        
        print(f"Found {len(messages)} messages.")
        
        # Some basic stats for verification
        system_messages = sum(1 for msg in messages if msg.get('is_system', False))
        deleted_messages = sum(1 for msg in messages if msg.get('is_deleted', False))
        edited_messages = sum(1 for msg in messages if msg.get('is_edited', False))
        
        print(f"Message breakdown:")
        print(f"  - Regular messages: {len(messages) - system_messages}")
        print(f"  - System messages: {system_messages}")
        print(f"  - Deleted messages: {deleted_messages}")
        print(f"  - Edited messages: {edited_messages}")
        
        # Get list of senders
        senders = set(msg['sender'] for msg in messages if not msg.get('is_system', False))
        print(f"Chat participants: {', '.join(sorted(senders))}")
        
    except Exception as e:
        print(f"Error parsing chat: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Extract media files
    media_files = extract_media_files(zip_path, output_dir)
    print(f"Extracted {len(media_files)} media files.")
    
    # Generate HTML
    output_file = os.path.join(output_dir, 'index.html')
    generate_html(messages, media_files, output_file)
    
    print(f"Conversion complete! Output saved to: {output_dir}")
    print(f"Open {output_file} in your browser to view the chat.")

if __name__ == "__main__":
    main()
