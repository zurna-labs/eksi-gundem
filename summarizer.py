import tiktoken

class Summarizer:

    def __init__(self, openai_client, log):
        self.model = 'gpt-3.5-turbo'
        self.token_encoding = "cl100k_base"
        self.summarization_prompt = "\n\Yazılanları en fazla 3 cümlede özetle."
        self.model_token_limit = 4000
        self.log = log
        self.openai_client = openai_client

    def num_tokens_from_string(self, string: str) -> int:
        encoding = tiktoken.get_encoding(self.token_encoding)
        num_tokens = len(encoding.encode(string))
        return num_tokens

    def summarize(self, entries):

        prompt_token_count = self.num_tokens_from_string(self.summarization_prompt)

        entries_stack = list(entries)
        summaries_stack = []
        current_text_body = ""

        summarized_at_least_once = False

        while entries_stack or summaries_stack:
            entry = entries_stack.pop() if entries_stack else summaries_stack.pop()
            current_token_count = self.num_tokens_from_string(current_text_body)
            new_token_count = self.num_tokens_from_string(entry)
            if not entry or entry == "görsel" or entry == "görselgörsel":
                continue
            if new_token_count + prompt_token_count > self.model_token_limit:
                # continue
                self.log("> Split entry in half")
                entry_second_half = entry[len(entry)//2:]
                entry = entry[:len(entry)//2]
                entries_stack.insert(0, entry_second_half)
            if current_token_count + new_token_count + prompt_token_count >= self.model_token_limit:
                summary = self.call_openai(current_text_body)
                self.log("> Add summary to summaries stack, with token count " + str(self.num_tokens_from_string(summary)))
                summaries_stack.append(summary)
                summarized_at_least_once = True
                current_text_body = entry
            else:
                current_text_body += '\n-------\n'
                current_text_body += entry

        final_summary = self.call_openai(current_text_body)

        return final_summary

    def call_openai(self, text_to_summarize):
        self.log('+ Calling OpenAI -- ')
        # Use OpenAI API for summarization
        try:
            response = self.openai_client.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type":"text",
                                "text": text_to_summarize + self.summarization_prompt
                            }
                        ]
                    }
                ],
                max_tokens=300
            )
            summary_text = response['choices'][0]["message"]["content"]
            self.log('- OpenAI call finished')
            return summary_text
        except Exception as e:
            self.log("- Problem! " + str(e))
            return None
