"""
VTT (WebVTT) to text conversion utility
Handles Zoom's VTT transcript format
"""

import re
from typing import Union
import webvtt
from io import StringIO


def vtt_to_text(vtt_content: Union[str, bytes]) -> str:
    """
    Convert VTT content to plain text
    
    Args:
        vtt_content: VTT file content as string or bytes
        
    Returns:
        Plain text transcript with timestamps removed
    """
    try:
        # Convert bytes to string if needed
        if isinstance(vtt_content, bytes):
            vtt_content = vtt_content.decode('utf-8', errors='replace')
        
        # Remove BOM if present
        if vtt_content.startswith('\ufeff'):
            vtt_content = vtt_content[1:]
        
        # Parse VTT content
        buffer = StringIO(vtt_content)
        captions = []
        
        # Use webvtt library to parse
        for caption in webvtt.read_buffer(buffer):
            # Clean up the text
            text = caption.text.strip()
            
            # Remove speaker labels if present (format: "Speaker: text")
            if ':' in text and len(text.split(':')[0]) < 30:
                parts = text.split(':', 1)
                if len(parts) == 2:
                    text = parts[1].strip()
            
            # Remove any HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            
            # Remove multiple spaces
            text = re.sub(r'\s+', ' ', text)
            
            if text:
                captions.append(text)
        
        # Join captions with spaces (not newlines) to maintain flow
        full_text = ' '.join(captions)
        
        # Clean up duplicate spaces and normalize
        full_text = re.sub(r'\s+', ' ', full_text)
        full_text = full_text.strip()
        
        return full_text if full_text else "No transcript content found."
        
    except Exception as e:
        # Fallback: try simple regex extraction
        try:
            # Remove VTT header and timestamps
            lines = vtt_content.split('\n') if isinstance(vtt_content, str) else vtt_content.decode('utf-8').split('\n')
            text_lines = []
            
            for line in lines:
                line = line.strip()
                
                # Skip empty lines, timestamps, and VTT headers
                if not line or 'WEBVTT' in line or '-->' in line:
                    continue
                    
                # Skip lines that look like cue identifiers (usually numbers or IDs)
                if line.isdigit() or (len(line) < 10 and not ' ' in line):
                    continue
                
                # Remove HTML tags
                line = re.sub(r'<[^>]+>', '', line)
                
                if line:
                    text_lines.append(line)
            
            return ' '.join(text_lines) if text_lines else "No transcript content found."
            
        except Exception as fallback_error:
            return f"Error processing VTT content: {str(e)}"


def extract_speakers_from_vtt(vtt_content: Union[str, bytes]) -> dict:
    """
    Extract speaker information from VTT content
    
    Args:
        vtt_content: VTT file content
        
    Returns:
        Dictionary mapping speakers to their dialogue counts
    """
    speakers = {}
    
    try:
        if isinstance(vtt_content, bytes):
            vtt_content = vtt_content.decode('utf-8', errors='replace')
        
        buffer = StringIO(vtt_content)
        
        for caption in webvtt.read_buffer(buffer):
            text = caption.text.strip()
            
            # Look for speaker pattern (e.g., "John: Hello")
            if ':' in text and len(text.split(':')[0]) < 30:
                speaker = text.split(':')[0].strip()
                if speaker and not speaker.isdigit():
                    speakers[speaker] = speakers.get(speaker, 0) + 1
    except:
        pass
    
    return speakers


def get_vtt_duration(vtt_content: Union[str, bytes]) -> float:
    """
    Get total duration of VTT content in seconds
    
    Args:
        vtt_content: VTT file content
        
    Returns:
        Duration in seconds, or 0 if unable to parse
    """
    try:
        if isinstance(vtt_content, bytes):
            vtt_content = vtt_content.decode('utf-8', errors='replace')
        
        buffer = StringIO(vtt_content)
        captions = list(webvtt.read_buffer(buffer))
        
        if captions:
            last_caption = captions[-1]
            # Parse end timestamp (format: HH:MM:SS.mmm or MM:SS.mmm)
            end_time = last_caption.end
            
            # Convert timestamp to seconds
            parts = end_time.split(':')
            if len(parts) == 3:
                hours, minutes, seconds = parts
                total_seconds = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            elif len(parts) == 2:
                minutes, seconds = parts
                total_seconds = int(minutes) * 60 + float(seconds)
            else:
                total_seconds = float(end_time)
            
            return total_seconds
    except:
        pass
    
    return 0.0