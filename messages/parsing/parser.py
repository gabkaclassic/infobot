import os

from messages.message_node import MessageNode
from utils.image_utils import prepare_image, get_image_path
from uuid import uuid4 as uuid


nodes_ids = dict()

def parse_message_tree():
    messages_tree = None
    file_path = os.path.join('trees', 'tree.txt')

    with open(file_path, 'r', encoding='utf-8') as file:
        for line in file:
            if not line.strip():
                continue

            parts = line.split('|')
            text = (
                parts[1].strip()
                .replace('\\n', '\n')
                .replace('.', '\.')
                .replace('!', '\!')
                .replace('#', '\#')
                .replace('+', '\+')
                .replace('=', '\=')
                .replace('-', '\-')
                .replace('(', '\(')
                .replace(')', '\)')
            )
            node_id = parts[0].strip()
            short_text = parts[2].strip()
            image_path = get_image_path(parts[3].strip()) if parts[3].strip() else None
            if image_path:
                image_path = prepare_image(image_path)

            node = MessageNode(text, short_text, image_path)
            if messages_tree:
                messages_tree.add_node(node_id, node)
                short_node_id = str(uuid())
                nodes_ids[short_node_id] = node_id
                nodes_ids[node_id] = short_node_id
            else:
                messages_tree = node
    return messages_tree
