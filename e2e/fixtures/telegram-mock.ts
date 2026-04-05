import axios from "axios";

const API_URL = "http://localhost:8000";

export async function simulateStartCommand(botToken: string, chatId: number, code: string, username: string = "testuser") {
  const update = {
    update_id: Date.now(),
    message: {
      message_id: Date.now(),
      from: { id: chatId, is_bot: false, first_name: "Test", username },
      chat: { id: chatId, type: "private" },
      text: `/start ${code}`,
    },
  };
  return axios.post(`${API_URL}/api/telegram/webhook/${botToken}`, update);
}

export async function simulateCommand(botToken: string, chatId: number, command: string) {
  const update = {
    update_id: Date.now(),
    message: {
      message_id: Date.now(),
      from: { id: chatId, is_bot: false, first_name: "Test" },
      chat: { id: chatId, type: "private" },
      text: command,
    },
  };
  return axios.post(`${API_URL}/api/telegram/webhook/${botToken}`, update);
}
