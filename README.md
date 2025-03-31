# WhatsApp Chat Archive to HTML Converter

This tool converts WhatsApp chat export archives (ZIP files) into beautifully formatted HTML files for easy viewing and sharing.

## Features

- **Enhanced Chat Viewing**: Clean, WhatsApp-style message bubbles with proper formatting
- **Media Support**: Displays images, videos, and other media contained in the export
- **Interactive Controls**: Easily switch between viewing perspectives (sent/received)
- **Customizable Display Options**:
  - Toggle dialog text visibility
  - Toggle media visibility
  - Filter conversations by date range
- **Responsive Design**: Works on desktop and mobile browsers
- **WhatsApp Formatting**: Preserves message formatting (bold, italic, strikethrough, etc.)
- **Preserves Original Structure**: Maintains timestamps, sender information, and media attachments
- **Export Handling**: Displays system messages, deleted messages, and edited messages

## Usage

1. Export a chat from WhatsApp mobile (Settings → Chats → Export chat)
2. Run the converter:
   ```
   python3 whatsapp-to-html.py <path-to-zip-file>
   ```
3. Open the generated `index.html` file in your browser

## Control Panel Features

The interactive control panel can be toggled and docked to either side of the screen, offering:

- **Perspective Selection**: Choose which participant's messages appear on the right side
- **Content Filters**: Show/hide message text or media independently
- **Date Filtering**: View messages from specific date ranges
- **Export Information**: Learn about the limitations of WhatsApp exports
- **Position Controls**: Dock the panel to your preferred side or minimize it

## Export Limitations

WhatsApp chat exports have some inherent limitations that this tool cannot overcome:

- Message replies are not preserved (no indication of which message was replied to)
- Emoji reactions are not included
- Media quality may be reduced
- Some advanced formatting or interactive content may be lost

## Requirements

- Python 3.6 or higher
- Standard Python libraries: os, sys, re, zipfile, shutil, datetime

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
