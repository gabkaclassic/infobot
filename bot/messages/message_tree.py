from bot.messages.message_node import MessageNode
from bot.messages.parsing.parser import parse_message_tree

messages_tree = parse_message_tree()


def get_message_node(node_id):
    keys = node_id.split('.')
    result = messages_tree
    for key in keys:
        result = result.get(key, {})
        if not result:
            return None

    if isinstance(result, MessageNode):
        return result
    else:
        return None
