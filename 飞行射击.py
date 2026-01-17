import pygame
import random
import sys
from typing import Dict, List, Optional
import math

# --- 游戏配置 ---
class GameConfig:
    # 屏幕设置
    SCREEN_WIDTH = 480
    SCREEN_HEIGHT = 640
    FPS = 60
    
    # 颜色定义
    WHITE = (255, 255, 255)
    BLACK = (0, 0, 0)
    RED = (255, 0, 0)
    GREEN = (0, 255, 0)
    BLUE = (0, 0, 255)
    YELLOW = (255, 255, 0)
    
    # 玩家设置
    PLAYER_SPEED = 5
    PLAYER_SHOOT_DELAY = 250  # 发射延迟(毫秒)
    PLAYER_INVINCIBLE_TIME = 2000  # 无敌时间(毫秒)

# --- 玩家类 ---
class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        # 基础属性
        self.image = pygame.Surface((50, 40))
        self.image.fill(GameConfig.BLUE)
        self.rect = self.image.get_rect()
        self.rect.centerx = GameConfig.SCREEN_WIDTH // 2
        self.rect.bottom = GameConfig.SCREEN_HEIGHT - 10
        
        # 移动相关
        self.speed = GameConfig.PLAYER_SPEED
        self.velocity_x = 0
        self.velocity_y = 0
        
        # 射击相关
        self.last_shot = 0
        self.shoot_delay = GameConfig.PLAYER_SHOOT_DELAY
        self.power_level = 1  # 武器等级
        
        # 状态相关
        self.lives = 3
        self.score = 0
        self.is_invincible = False
        self.invincible_timer = 0
        self.alpha = 255  # 用于无敌状态闪烁效果

    def update(self):
        # 处理移动
        keystate = pygame.key.get_pressed()
        self.velocity_x = 0
        if keystate[pygame.K_LEFT]:
            self.velocity_x = -self.speed
        if keystate[pygame.K_RIGHT]:
            self.velocity_x = self.speed
            
        # 应用移动
        self.rect.x += self.velocity_x
        
        # 边界检查
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > GameConfig.SCREEN_WIDTH:
            self.rect.right = GameConfig.SCREEN_WIDTH
            
        # 处理无敌状态
        if self.is_invincible:
            current_time = pygame.time.get_ticks()
            if current_time - self.invincible_timer > GameConfig.PLAYER_INVINCIBLE_TIME:
                self.is_invincible = False
                self.alpha = 255
            else:
                # 闪烁效果
                self.alpha = 128 + math.sin(current_time * 0.01) * 127

    def shoot(self, bullets_group, all_sprites):
        current_time = pygame.time.get_ticks()
        if current_time - self.last_shot > self.shoot_delay:
            self.last_shot = current_time
            
            if self.power_level == 1:
                # 单发子弹
                bullet = Bullet(self.rect.centerx, self.rect.top)
                bullets_group.add(bullet)
                all_sprites.add(bullet)
            elif self.power_level == 2:
                # 双发子弹
                for offset in [-10, 10]:
                    bullet = Bullet(self.rect.centerx + offset, self.rect.top)
                    bullets_group.add(bullet)
                    all_sprites.add(bullet)
            else:
                # 三发散射
                for angle in [-15, 0, 15]:
                    bullet = Bullet(self.rect.centerx, self.rect.top, angle=angle)
                    bullets_group.add(bullet)
                    all_sprites.add(bullet)
    
    def take_damage(self):
        if not self.is_invincible:
            self.lives -= 1
            self.is_invincible = True
            self.invincible_timer = pygame.time.get_ticks()
            return True
        return False
    
    def power_up(self):
        if self.power_level < 3:
            self.power_level += 1
            
    def add_score(self, points: int):
        self.score += points

# --- 玩家子弹类 ---
class Bullet(pygame.sprite.Sprite):
    def __init__(self, x, y, angle=0):
        super().__init__()
        self.image = pygame.Surface((5, 10))
        self.image.fill(GameConfig.WHITE)
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.bottom = y
        self.speed = -10
        self.angle = angle

    def update(self):
        self.rect.y += self.speed
        if self.angle != 0:
            self.rect.x += math.sin(math.radians(self.angle)) * self.speed
        if self.rect.bottom < 0:
            self.kill()

# --- 敌方子弹类 ---
class EnemyBullet(pygame.sprite.Sprite):
    def __init__(self, x, y, speed, speedx=0):
        super().__init__()
        self.image = pygame.Surface((5, 10))
        self.image.fill(GameConfig.YELLOW)
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.top = y
        self.speed = speed      # 垂直速度
        self.speedx = speedx    # 水平速度

    def update(self):
        self.rect.y += self.speed
        self.rect.x += self.speedx
        if (self.rect.top > GameConfig.SCREEN_HEIGHT or 
            self.rect.right < 0 or 
            self.rect.left > GameConfig.SCREEN_WIDTH):
            self.kill()

# --- 小兵类（美化图案）---
class Minion(pygame.sprite.Sprite):
    def __init__(self, level):
        super().__init__()
        # 使用透明背景，绘制多边形飞船外形
        self.image = pygame.Surface((40, 30), pygame.SRCALPHA)
        pygame.draw.polygon(self.image, (255, 100, 100), [(0, 30), (20, 0), (40, 30)])
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(0, GameConfig.SCREEN_WIDTH - self.rect.width)
        self.rect.y = random.randrange(-100, -40)
        self.speedy = random.randrange(1, 2) + level * 0.5
        self.speedx = random.choice([-1, 1]) * random.uniform(0.5, 1.5)
        # 发射子弹的计时器
        self.shoot_delay = random.randint(60, 120)  # 帧数
        self.frame_count = 0

    def update(self):
        self.rect.y += self.speedy
        self.rect.x += self.speedx
        if self.rect.left < 0 or self.rect.right > GameConfig.SCREEN_WIDTH:
            self.speedx *= -1
        if self.rect.top > GameConfig.SCREEN_HEIGHT:
            self.kill()
        self.frame_count += 1
        if self.frame_count >= self.shoot_delay:
            self.frame_count = 0
            # 小兵子弹只作垂直发射
            enemy_bullet = EnemyBullet(self.rect.centerx, self.rect.bottom, speed=5)
            self.groups()['enemy_bullets'].add(enemy_bullet)
            self.groups()['all_sprites'].add(enemy_bullet)

# --- BOSS类（美化图案及多子弹发射） ---
class Boss(pygame.sprite.Sprite):
    def __init__(self, level):
        super().__init__()
        # 使用透明背景，组合椭圆和矩形绘制BOSS外形
        self.image = pygame.Surface((100, 80), pygame.SRCALPHA)
        pygame.draw.ellipse(self.image, (100, 255, 100), [0, 0, 100, 60])
        pygame.draw.rect(self.image, (0, 200, 0), (20, 60, 60, 20))
        self.rect = self.image.get_rect()
        self.rect.centerx = GameConfig.SCREEN_WIDTH // 2
        self.rect.y = -self.rect.height
        self.speedy = 1 + level * 0.3
        self.health = 10 + level * 5
        self.active = False  # 小兵未清除前不激活
        self.shoot_delay = 90  # 帧数间隔
        self.frame_count = 0

    def update(self):
        # 从上方缓慢进入屏幕
        if self.rect.y < GameConfig.SCREEN_HEIGHT // 4:
            self.rect.y += self.speedy
        # 激活后开始发射子弹
        if self.active:
            self.frame_count += 1
            if self.frame_count >= self.shoot_delay:
                self.frame_count = 0
                bullet_speed = 7
                # 同时发射3枚子弹，形成左右分散效果
                offsets = [-3, 0, 3]  # 水平偏移速度
                for offset in offsets:
                    enemy_bullet = EnemyBullet(self.rect.centerx, self.rect.bottom, speed=bullet_speed, speedx=offset)
                    self.groups()['enemy_bullets'].add(enemy_bullet)
                    self.groups()['all_sprites'].add(enemy_bullet)

    def take_damage(self, damage):
        self.health -= damage
        if self.health <= 0:
            self.kill()
            return True
        return False

# --- 辅助函数：向精灵添加公共分组引用 ---
def add_groups(sprite, groups_dict):
    sprite._groups = groups_dict
    sprite.groups = lambda: sprite._groups

# --- 游戏主函数 ---
def main():
    pygame.init()
    screen = pygame.display.set_mode((GameConfig.SCREEN_WIDTH, GameConfig.SCREEN_HEIGHT))
    pygame.display.set_caption("经典飞行射击游戏")
    clock = pygame.time.Clock()

    level = 1
    max_level = 10
    lives = 3

    # 精灵分组管理
    all_sprites = pygame.sprite.Group()
    minions_group = pygame.sprite.Group()      # 小兵分组
    boss_group = pygame.sprite.Group()
    bullets_group = pygame.sprite.Group()        # 玩家子弹分组
    enemy_bullets_group = pygame.sprite.Group()    # 敌方子弹分组

    groups_dict = {
        'all_sprites': all_sprites,
        'minions_group': minions_group,
        'boss_group': boss_group,
        'bullets_group': bullets_group,
        'enemy_bullets': enemy_bullets_group
    }

    player = Player()
    all_sprites.add(player)
    add_groups(player, groups_dict)

    def start_level(current_level):
        # 生成小兵：数量随关卡增加
        for i in range(5 + current_level):
            minion = Minion(current_level)
            add_groups(minion, groups_dict)
            all_sprites.add(minion)
            minions_group.add(minion)
        # 生成BOSS
        boss = Boss(current_level)
        add_groups(boss, groups_dict)
        all_sprites.add(boss)
        boss_group.add(boss)

    start_level(level)

    running = True
    while running:
        clock.tick(GameConfig.FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    player.shoot(bullets_group, all_sprites)

        all_sprites.update()

        # 玩家子弹击中小兵
        hits_minion = pygame.sprite.groupcollide(minions_group, bullets_group, True, True)
        # 玩家子弹击中BOSS（仅在BOSS激活时有效）
        for boss in boss_group:
            if boss.active:
                hits_boss = pygame.sprite.spritecollide(boss, bullets_group, True)
                if hits_boss:
                    if boss.take_damage(len(hits_boss)):
                        boss_group.remove(boss)

        # 敌方子弹与玩家碰撞
        hits_enemy_bullet = pygame.sprite.spritecollide(player, enemy_bullets_group, True)
        if hits_enemy_bullet:
            lives -= 1
            if lives <= 0:
                level = 1
                lives = 3
            player.rect.centerx = GameConfig.SCREEN_WIDTH // 2
            player.rect.bottom = GameConfig.SCREEN_HEIGHT - 10

        # 小兵和BOSS碰撞玩家
        hit_minion_player = pygame.sprite.spritecollide(player, minions_group, True)
        hit_boss_player = pygame.sprite.spritecollide(player, boss_group, False)
        if hit_minion_player or hit_boss_player:
            lives -= 1
            if lives <= 0:
                level = 1
                lives = 3
            player.rect.centerx = GameConfig.SCREEN_WIDTH // 2
            player.rect.bottom = GameConfig.SCREEN_HEIGHT - 10

        # 当所有小兵清除后，激活所有BOSS
        if len(minions_group) == 0:
            for boss in boss_group:
                boss.active = True

        # 本关小兵及BOSS全被清除后进入下一关
        if len(minions_group) == 0 and len(boss_group) == 0:
            if level >= max_level:
                print("恭喜你通过所有关卡！")
                running = False
            else:
                level += 1
                bullets_group.empty()
                enemy_bullets_group.empty()
                start_level(level)

        screen.fill(GameConfig.BLACK)
        all_sprites.draw(screen)
        font = pygame.font.SysFont("arial", 20)
        info_text = f"关卡: {level}  生命: {lives}"
        text_surface = font.render(info_text, True, GameConfig.WHITE)
        screen.blit(text_surface, (10, 10))
        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
