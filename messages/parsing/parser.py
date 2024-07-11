import os

from messages.message_node import MessageNode


def get_image_path(filename: str):
    return os.path.join('messages', 'parsing', 'images', f'{filename}.jpg')


def parse_message_tree():
    messages_tree = None
    file_path = os.path.join('messages', 'parsing', 'trees', 'test')

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if not line:
                continue

            parts = line.split('|')
            node_id = parts[0].strip()
            text = parts[1].strip().replace('\\n', '\n')
            short_text = parts[2].strip()
            image = get_image_path(parts[3].strip()) if parts[3].strip() else None
            node = MessageNode(text, short_text, image)
            if messages_tree:
                messages_tree.add_node(node_id, node)
            else:
                messages_tree = node
    return messages_tree
