import asyncio, traceback
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, selectinload
from sqlalchemy.future import select
from contextlib import asynccontextmanager
from typing import List, Tuple
from .models import *
from .config import DATABASE_SETTINGS

DATABASE_URI = URL.create(**DATABASE_SETTINGS)


class WorldDB:
    def __init__(self):
        self.engine = create_async_engine(DATABASE_URI, echo=True)

    def async_session_generator(self):
        return sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    @asynccontextmanager
    async def session(self):
        async_session = self.async_session_generator()

        async with async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                traceback.print_exc()
                raise e
            finally:
                await session.close()

    async def recreate_database(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def populate_database(self):
        async with self.session() as session:
            map = Map(name="Placeholder Map")
            session.add(map)

    ################################## CREATE ##################################

    async def create_user(self, uuid: str):
        async with self.session() as session:
            user = User(uuid=uuid)
            session.add(user)

    async def create_character(self, user_id: int, character_attributes: dict, character_properties: dict):
        async with self.session() as session:
            character = Character(
                name=character_attributes["name"],
                user_id=user_id
            )
            session.add(character)

    ################################### READ ###################################

    async def get_user_by_uuid(self, user_uuid: str) -> User:
        async with self.session() as session:
            statement = select(User).where(User.uuid == user_uuid)
            result = await session.execute(statement)
            user = result.scalars().one()
            return user

    async def get_user_id_by_uuid(self, user_uuid: str) -> int:
        async with self.session() as session:
            statement = select(User.id).where(User.uuid == user_uuid)
            result = await session.execute(statement)
            user_id = result.scalars().one()
            return user_id

    async def get_user_characters(self, user_id: int) -> List[Character]:
        async with self.session() as session:
            statement = select(User, user_id).options(selectinload(User.characters))
            result = await session.execute(statement)
            user = result.scalars().one()
            return list(user.characters)

    async def get_user_character_uuids(self, user_id: int) -> List[str]:
        async with self.session() as session:
            statement = select(Character.uuid).where(Character.user_id == user_id)
            result = await session.execute(statement)
            character_uuids = result.scalars()
            return list(character_uuids)

    async def get_user_max_characters(self, user_id: int) -> int:
        async with self.session() as session:
            statement = select(User.max_characters).where(User.id == user_id)
            result = await session.execute(statement)
            max_characters = result.scalar()
            return max_characters

    async def get_character_by_uuid(self, character_uuid: str) -> Character:
        async with self.session() as session:
            statement = select(Character).where(Character.uuid == character_uuid)
            result = await session.execute(statement)
            character = result.scalars().one()
            return character

    async def get_character_uuid_by_name(self, name: str) -> str:
        async with self.session() as session:
            statement = select(Character.uuid).where(Character.name == name)
            result = await session.execute(statement)
            character_uuid = result.scalar()
            return character_uuid

    async def get_character_location_by_uuid(self, character_uuid: str) -> Tuple[int, float, float]:
        async with self.session() as session:
            statement = select(Character).where(Character.uuid == character_uuid)
            result = await session.execute(statement)
            character = result.scalars().one()
            return character.map_id, character.x, character.y

    async def check_character_name_exists(self, name: str) -> bool:
        async with self.session() as session:
            statement = select(Character).where(Character.name == name)
            result = await session.execute(statement)
            character = result.scalars().one_or_none()
            return character is not None

    async def check_user_has_max_characters(self, user_id: int) -> bool:
        async with self.session() as session:
            character_uuids, max_characters = await asyncio.gather(self.get_user_character_uuids(user_id), self.get_user_max_characters(user_id))
            return len(character_uuids) == max_characters

    ################################## UPDATE ##################################

    async def update_chracter_by_uuid(self, character_uuid: str, player: dict):
        async with self.session() as session:
            statement = select(Character).where(Character.uuid == character_uuid)
            result = await session.execute(statement)
            character = result.scalars().one()
            character.map_id = player.get("map_id")
            character.x, character.y = player.get("position")
            await session.merge(character)

    async def delete_character_by_uuid(self, character_uuid: str):
        async with self.session() as session:
            statement = select(Character).where(Character.uuid == character_uuid)
            result = await session.execute(statement)
            character = result.scalars().one()
            character.is_deleted = True
            await session.merge(character)

    ################################## DELETE ##################################
