<img width="2688" height="1536" alt="atat" src="https://github.com/user-attachments/assets/17e80468-98b9-4761-8ee5-fb8bb1f7e1c5" />




# 🤖 AT-AT (Api Testing & A/B Testing)
Автоматизированная агентная система тестирования API и пользовательских интерфейсов с поддержкой генерации тест-кейсов, моделирования поведения пользователей и A/B-аналитики.

---
## 📋 Требования

Перед запуском должны быть установлены:
- Docker
- Docker Compose
- Git

---
## 🚀 Запуск
> [!NOTE]
> Есть **временные** трудности с запуском системы с frontend-частью
1. ```git clone <repository-url>```
2. ```cd at-at```
3. ```make up```

--- 
## 🌐 Доступные сервисы

После запуска будут доступны:
|  **Сервис** |           **URL**          |
|:-----------:|:--------------------------:|
|   Frontend  |    http://localhost:3000   |
| Backend API |    http://localhost:8000   |
|  Swagger UI | http://localhost:8000/docs |

---
## 🛠 Используемые технологии
### Backend
- Python
- FastAPI
- FastStream
- RabbitMQ
- LangChain
- LangGraph

### API Testing
- Schemathesis
- Hypothesis
- OpenAPI / Swagger

### UI Testing
- Playwright
- Browser Automation
- Agent-based Testing

### Frontend
- React
- TypeScript

### Infrastructure
- Docker
- Docker Compose
- Git

---
## 📚 Документация подсистем
### 🔌 API Testing
Подсистема автоматизированного тестирования API:
➡️ [API Testing README](project/apps/api_agent/README.md)

### 🖥️ UI & A/B Testing
Подсистема агентного тестирования интерфейсов и A/B-аналитики:
➡️ [UI Testing README](project/apps/ab_agent/README.md)

---
## ✨ Возможности системы
- Генерация тест-кейсов на основе спецификаций
- Автоматическое тестирование REST API
- Тестирование бизнес-процессов
- Генерация агентных сценариев
- Имитация поведения пользователей
- Массовое выполнение UI-тестов
- Сбор аналитики и метрик
- A/B-анализ интерфейсов
- Формирование отчетов и тестовых артефактов
