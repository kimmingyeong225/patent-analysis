from sqlalchemy import Column, Integer, String, Boolean, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from database import Base

class SearchResult(Base):
    __tablename__ = "search_results"

    id = Column(Integer, primary_key=True, index=True)
    query = Column(String, index=True)
    patent_id = Column(String, index=True)
    rank = Column(Integer)
    similarity_score = Column(Float)

    patent = relationship("Patent", back_populates="search_results")


class Patent(Base):
    __tablename__ = "patents"

    id = Column(Integer, primary_key=True, index=True)
    patent_id = Column(String, unique=True, index=True)
    application_number = Column(String)
    title = Column(String)
    applicant = Column(String)
    inventor = Column(String)
    application_date = Column(String)
    publication_date = Column(String)
    registration_date = Column(String, nullable=True)
    abstract = Column(Text)
    claims = Column(JSON) # JSON type for list of strings
    doc_type = Column(String)

    # relations
    search_results = relationship("SearchResult", back_populates="patent")
    citation = relationship("Citation", back_populates="patent", uselist=False)
    legal_status = relationship("LegalStatus", back_populates="patent", uselist=False)
    classifications = relationship("Classification", back_populates="patent")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    patent_id = Column(String, ForeignKey("patents.patent_id"))
    cited_by_count = Column(Integer, default=0)
    citing_count = Column(Integer, default=0)
    cited_patents = Column(JSON) # List of patent IDs

    patent = relationship("Patent", back_populates="citation")


class LegalStatus(Base):
    __tablename__ = "legal_statuses"

    id = Column(Integer, primary_key=True, index=True)
    patent_id = Column(String, ForeignKey("patents.patent_id"))
    status = Column(String)
    status_code = Column(String)
    last_event = Column(String)
    last_event_date = Column(String)
    is_alive = Column(Boolean)

    patent = relationship("Patent", back_populates="legal_status")


class Classification(Base):
    __tablename__ = "classifications"

    id = Column(Integer, primary_key=True, index=True)
    patent_id = Column(String, ForeignKey("patents.patent_id"))
    code_type = Column(String) # "ipc" or "cpc"
    code = Column(String)
    desc = Column(String)

    patent = relationship("Patent", back_populates="classifications")
