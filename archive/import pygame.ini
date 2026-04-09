import pygame
import random
import sys

# 初始化 Pygame
pygame.init()

# === 游戏常量设置 ===
WINDOW_WIDTH = 800        # 游戏窗口宽度
WINDOW_HEIGHT = 600       # 游戏窗口高度
GRID_SIZE = 20            # 网格大小
GRID_WIDTH = WINDOW_WIDTH // GRID_SIZE   # 横向格子数
GRID_HEIGHT = WINDOW_HEIGHT // GRID_SIZE   # 纵向格子数

# 颜色定义
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED   = (255, 0, 0)
GREEN = (0, 255, 0)

# 方向常量
UP    = (0, -1)
DOWN  = (0, 1)
LEFT  = (-1, 0)
RIGHT = (1, 0)

# 建立游戏窗口
window = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
pygame.display.set_caption("贪食蛇游戏")

# === 定义蛇类 ===
class Snake:
    def __init__(self):
        self.positions = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]  # 初始位置放在屏幕中央
        self.direction = random.choice([UP, DOWN, LEFT, RIGHT])
        self.length = 1
        self.color = GREEN

    def move(self):
        head_x, head_y = self.positions[0]
        dx, dy = self.direction
        new_head = ((head_x + dx) % GRID_WIDTH, (head_y + dy) % GRID_HEIGHT)
        # 检查是否撞到自身（从第二个位置开始检查）
        if new_head in self.positions[1:]:
            self.reset()
        else:
            self.positions.insert(0, new_head)
            if len(self.positions) > self.length:
                self.positions.pop()

    def reset(self):
        """撞到自身后重置蛇的状态"""
        self.positions = [(GRID_WIDTH // 2, GRID_HEIGHT // 2)]
        self.direction = random.choice([UP, DOWN, LEFT, RIGHT])
        self.length = 1

    def change_direction(self, new_direction):
        # 禁止直接反向（例如当前向上，不能直接向下）
        if (new_direction[0] * -1, new_direction[1] * -1) == self.direction:
            return
        self.direction = new_direction

    def draw(self, surface):
        for pos in self.positions:
            rect = pygame.Rect(pos[0] * GRID_SIZE, pos[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE)
            pygame.draw.rect(surface, self.color, rect)

# === 定义食物类 ===
class Food:
    def __init__(self):
        self.position = (0, 0)
        self.color = RED
        self.randomize_position()

    def randomize_position(self):
        self.position = (random.randint(0, GRID_WIDTH - 1),
                         random.randint(0, GRID_HEIGHT - 1))

    def draw(self, surface):
        rect = pygame.Rect(self.position[0] * GRID_SIZE, self.position[1] * GRID_SIZE, GRID_SIZE, GRID_SIZE)
        pygame.draw.rect(surface, self.color, rect)

# === 主函数 ===
def main():
    clock = pygame.time.Clock()             # 控制游戏刷新速度
    snake = Snake()                         # 创建蛇对象
    food = Food()                           # 创建食物对象
    score = 0                               # 游戏得分
    font = pygame.font.SysFont(None, 36)      # 设置文字样式

    while True:
        # 事件处理：退出和方向控制
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    snake.change_direction(UP)
                elif event.key == pygame.K_DOWN:
                    snake.change_direction(DOWN)
                elif event.key == pygame.K_LEFT:
                    snake.change_direction(LEFT)
                elif event.key == pygame.K_RIGHT:
                    snake.change_direction(RIGHT)
        
        # 更新蛇的位置
        snake.move()

        # 判断蛇是否吃到食物
        if snake.positions[0] == food.position:
            snake.length += 1
            score += 1
            food.randomize_position()

        # 绘制画面：背景、蛇、食物以及得分显示
        window.fill(BLACK)
        snake.draw(window)
        food.draw(window)
        score_text = font.render(f'Score: {score}', True, WHITE)
        window.blit(score_text, (10, 10))

        # 更新显示
        pygame.display.flip()
        clock.tick(10)  # 游戏速度，每秒 10 帧

if __name__ == '__main__':
    main()
