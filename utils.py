from discord.ext import commands

class AddPlayerState:
    def __init__(self):
        self.current_operations = {}

    def start_operation(self, user_id, channel_id):
        self.current_operations[user_id] = {
            'step': 'gamer_tag',
            'data': {},
            'channel_id': channel_id  # Track which channel initiated the command
        }

    def update_operation(self, user_id, data_key, value):
        if user_id in self.current_operations:
            self.current_operations[user_id]['data'][data_key] = value
            return True
        return False

    def get_current_step(self, user_id):
        if user_id in self.current_operations:
            return self.current_operations[user_id]['step']
        return None

    def get_channel_id(self, user_id):
        if user_id in self.current_operations:
            return self.current_operations[user_id]['channel_id']
        return None

    def advance_step(self, user_id):
        steps = ['gamer_tag', 'ingame_name', 'discord_tag']
        current = self.get_current_step(user_id)
        if current in steps:
            next_index = steps.index(current) + 1
            if next_index < len(steps):
                self.current_operations[user_id]['step'] = steps[next_index]
                return True
        return False

    def get_operation_data(self, user_id):
        return self.current_operations.get(user_id, {}).get('data', {})

    def cancel_operation(self, user_id):
        if user_id in self.current_operations:
            del self.current_operations[user_id]
            return True
        return False

    def is_in_progress(self, user_id):
        return user_id in self.current_operations

player_state = AddPlayerState()