import re
from typing import List, Sequence
from pydantic import Field
from llama_index.core.schema import BaseNode, MetadataMode
from llama_index.core.node_parser import NodeParser
from llama_index.core.node_parser.node_utils import build_nodes_from_splits

class ParagraphSplitter(NodeParser):
    separator: str = Field(
        default=r'\n{2,}',
        description="Regex pattern used to split text into paragraphs (e.g., 2+ newlines)."
    )
    strip_empty: bool = Field(
        default=True,
        description="Whether to remove empty or whitespace-only chunks."
    )

    def _parse_nodes(
        self,
        nodes: Sequence[BaseNode],
        show_progress: bool = False,
        **kwargs
    ) -> List[BaseNode]:
        all_nodes: List[BaseNode] = []

        for node in nodes:
            text = node.get_content(metadata_mode=MetadataMode.NONE)

            # Use regex to split on multiple newlines
            paragraphs = re.split(self.separator, text)

            cleaned = [
                p.strip() for p in paragraphs if not self.strip_empty or p.strip()
            ]

            all_nodes.extend(
                build_nodes_from_splits(cleaned, node, id_func=self.id_func)
            )

        return all_nodes