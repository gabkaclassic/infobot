from bot.messages.message_node import MessageNode
from utils.image_utils import prepare_image, get_image_path
import hashlib
import re

nodes_ids = dict()


def get_hash(input_string: str, algorithm: str = "sha256") -> str:
    hash_function = hashlib.new(algorithm)
    hash_function.update(input_string.encode("utf-8"))
    return hash_function.hexdigest()


def parse_message_tree(file_path: str):
    messages_tree = None

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            parts = line.split("|")
            text = (
                parts[1]
                .strip()
                .replace("\\n", "\n")
                .replace(".", "\.")
                .replace("!", "\!")
                .replace("#", "\#")
                .replace("+", "\+")
                .replace("=", "\=")
                .replace("-", "\-")
                .replace("(", "\(")
                .replace(")", "\)")
            )
            text = re.sub(r"(https?://\S+)_", r"\1\\_", text)
            node_id = parts[0].strip()
            short_text = parts[2].strip()
            image_path = get_image_path(parts[3].strip()) if parts[3].strip() else None
            if image_path:
                image_path = prepare_image(image_path)

            node = MessageNode(text, short_text, image_path)
            if messages_tree:
                messages_tree.add_node(node_id, node)
                short_node_id = get_hash(node_id)
                nodes_ids[short_node_id] = node_id
                nodes_ids[node_id] = short_node_id
            else:
                messages_tree = node

    return messages_tree, nodes_ids
