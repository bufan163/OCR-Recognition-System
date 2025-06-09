#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员账号初始化脚本
用于创建系统管理员账号
"""

import asyncio
import sys
from sqlalchemy.orm import Session
from database import SessionLocal, engine
from models import Base, User
from services.auth_service import AuthService
from utils.logger import setup_logger


def create_tables():
    """创建数据库表"""
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成")


async def init_admin_user():
    """初始化管理员用户"""
    logger = setup_logger("init_admin")
    auth_service = AuthService()
    
    db: Session = SessionLocal()
    try:
        # 检查是否已存在admin用户
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("管理员用户已存在")
            print(f"用户名: {existing_admin.username}")
            print(f"邮箱: {existing_admin.email}")
            print(f"是否为管理员: {existing_admin.is_admin}")
            print(f"创建时间: {existing_admin.created_at}")
            
            # 如果不是管理员，则更新为管理员
            if not existing_admin.is_admin:
                existing_admin.is_admin = True
                db.commit()
                print("已将现有admin用户设置为管理员")
            return existing_admin
        
        # 创建管理员用户
        print("正在创建管理员用户...")
        admin_user = await auth_service.register_user(
            db=db,
            username="admin",
            email="admin@ocr-system.com",
            password="123456",
            plan_type="enterprise",
            is_admin=True
        )
        
        print("管理员用户创建成功！")
        print(f"用户名: {admin_user.username}")
        print(f"邮箱: {admin_user.email}")
        print(f"密码: 123456")
        print(f"计划类型: {admin_user.plan_type}")
        print(f"是否为管理员: {admin_user.is_admin}")
        print(f"API配额: {admin_user.api_quota}")
        print(f"创建时间: {admin_user.created_at}")
        
        logger.info(f"管理员用户创建成功: {admin_user.username}")
        return admin_user
        
    except Exception as e:
        db.rollback()
        logger.error(f"创建管理员用户失败: {e}")
        print(f"创建管理员用户失败: {e}")
        raise
    finally:
        db.close()


def check_admin_exists():
    """检查管理员是否存在"""
    db: Session = SessionLocal()
    try:
        admin_users = db.query(User).filter(User.is_admin == True).all()
        if admin_users:
            print("\n当前系统中的管理员用户:")
            for admin in admin_users:
                print(f"- 用户名: {admin.username}, 邮箱: {admin.email}, 创建时间: {admin.created_at}")
        else:
            print("系统中暂无管理员用户")
        return admin_users
    finally:
        db.close()


async def main():
    """主函数"""
    print("OCR识别系统 - 管理员初始化工具")
    print("=" * 50)
    
    try:
        # 创建数据库表
        create_tables()
        
        # 检查现有管理员
        print("\n检查现有管理员用户...")
        check_admin_exists()
        
        # 初始化管理员用户
        print("\n初始化管理员用户...")
        await init_admin_user()
        
        # 再次检查管理员
        print("\n初始化完成，当前管理员用户:")
        check_admin_exists()
        
        print("\n" + "=" * 50)
        print("管理员初始化完成！")
        print("登录信息:")
        print("  用户名: admin")
        print("  密码: 123456")
        print("  管理员权限: 是")
        print("\n请及时修改默认密码以确保系统安全！")
        
    except Exception as e:
        print(f"初始化失败: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())