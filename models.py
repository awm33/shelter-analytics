from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Boolean,
    Enum,
    Index,
    func,
    text,
    ForeignKey,
    MetaData
)
from sqlalchemy.ext.declarative import declarative_base

metadata = MetaData()
BaseModel = declarative_base(metadata=metadata)

class Animal(BaseModel):
    __tablename__ = 'animals'

    id = Column(String, primary_key=True)
    shelter_id = Column(String, nullable=False)
    arn = Column(String)
    name = Column(String)
    species = Column(String)
    primary_breed = Column(String)
    secondary_bred = Column(String)
    gender = Column(String)
    pre_altered = Column(Boolean)
    chip_number = Column(String)
    chip_provider = Column(String)
    date_of_birth = Column(String)
    altered = Column(Boolean)
    primary_color = Column(String)
    secondary_color = Column(String)
    third_color = Column(String)
    color_pattern = Column(String)
    second_color_pattern = Column(String)
    size = Column(String)
    distinguishing_markings = Column(String)
    # purebred = Column(String) ## TODO: boolean?
    # adoption_price = Column() ## ???
    created_at = Column(DateTime,
                        nullable=False,
                        server_default=func.now())
    updated_at = Column(DateTime,
                        nullable=False,
                        server_default=func.now(),
                        onupdate=func.now())
