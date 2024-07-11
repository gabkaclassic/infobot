class MessageNode:
    def __init__(self, text: str, short_text: str, image: str = None):
        self.text = text
        self.image = image
        self.short_text = short_text
        self.choices = dict()

    def add_node(self, node_id, node, current=0):

        if isinstance(node_id, str):
            node_id = node_id.split('.')

        if current == len(node_id) - 1:
            node_id = '.'.join(node_id)
            self.choices[node_id] = node
            return

        self.choices.get('.'.join(node_id[:current + 1])).add_node(node_id, node, current + 1)

    def get_node(self, node_id, current=0):

        if not node_id:
            return

        if isinstance(node_id, str):
            node_id = node_id.split('.')

        if current == len(node_id) - 1:
            return self.choices.get('.'.join(node_id), None)

        return self.choices.get('.'.join(node_id[:current + 1])).get_node(node_id, current + 1)
