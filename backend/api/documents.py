from __future__ import annotations

import uuid
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..api.dependencies import get_db
from ..auth.jwt import get_current_user, require_roles
from ..models.models import DocumentFolder, GovernanceDocument, User
from ..schemas.schemas import (
    DocumentFolderCreate,
    DocumentFolderRead,
    DocumentFolderUpdate,
    DocumentTreeResponse,
    DocumentUploadResponse,
    GovernanceDocumentRead,
)
from ..services.storage import storage_service

router = APIRouter(prefix="/documents", tags=["documents"])

MANAGER_ROLES = ("BOARD", "SYSADMIN", "SECRETARY", "TREASURER")


def _build_document_read(document: GovernanceDocument) -> GovernanceDocumentRead:
    download_url = f"/documents/files/{document.id}/download"
    return GovernanceDocumentRead(
        id=document.id,
        folder_id=document.folder_id,
        title=document.title,
        description=document.description,
        content_type=document.content_type,
        file_size=document.file_size,
        uploaded_by_user_id=document.uploaded_by_user_id,
        created_at=document.created_at,
        download_url=download_url,
    )


def _serialize_folder(folder: DocumentFolder) -> DocumentFolderRead:
    documents = [_build_document_read(doc) for doc in sorted(folder.documents, key=lambda d: d.title.lower())]
    children = sorted(folder.children, key=lambda child: child.name.lower())
    return DocumentFolderRead(
        id=folder.id,
        name=folder.name,
        description=folder.description,
        parent_id=folder.parent_id,
        documents=documents,
        children=[_serialize_folder(child) for child in children],
    )


@router.get("/", response_model=DocumentTreeResponse)
def list_documents(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> DocumentTreeResponse:
    folders = (
        db.query(DocumentFolder)
        .order_by(DocumentFolder.name.asc())
        .all()
    )
    folder_map: Dict[int, DocumentFolder] = {folder.id: folder for folder in folders}
    root_folders = [folder for folder in folders if not folder.parent_id or folder.parent_id not in folder_map]
    uncategorized_docs = (
        db.query(GovernanceDocument)
        .filter(GovernanceDocument.folder_id.is_(None))
        .order_by(GovernanceDocument.title.asc())
        .all()
    )
    return DocumentTreeResponse(
        folders=[_serialize_folder(folder) for folder in root_folders],
        root_documents=[_build_document_read(doc) for doc in uncategorized_docs],
    )


@router.post("/folders", response_model=DocumentFolderRead)
def create_folder(
    payload: DocumentFolderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGER_ROLES)),
) -> DocumentFolderRead:
    folder = DocumentFolder(
        name=payload.name.strip(),
        description=payload.description,
        parent_id=payload.parent_id,
        created_by_user_id=user.id,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return _serialize_folder(folder)


@router.patch("/folders/{folder_id}", response_model=DocumentFolderRead)
def update_folder(
    folder_id: int,
    payload: DocumentFolderUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> DocumentFolderRead:
    folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(folder, key, value)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return _serialize_folder(folder)


@router.delete("/folders/{folder_id}", status_code=204)
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> Response:
    folder = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    for child in folder.children:
        child.parent_id = folder.parent_id
        db.add(child)
    db.flush()
    documents = db.query(GovernanceDocument).filter(GovernanceDocument.folder_id == folder_id).all()
    for document in documents:
        document.folder_id = folder.parent_id
        db.add(document)
    db.delete(folder)
    db.commit()
    return Response(status_code=204)


@router.post("/files", response_model=DocumentUploadResponse)
async def upload_document(
    folder_id: Optional[int] = Form(None),
    title: str = Form(...),
    description: Optional[str] = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGER_ROLES)),
) -> DocumentUploadResponse:
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="File is empty")
    extension = file.filename or "document"
    relative_path = f"governance/{uuid.uuid4().hex}_{extension}"
    stored = storage_service.save_file(relative_path, contents, content_type=file.content_type)
    document = GovernanceDocument(
        folder_id=folder_id,
        title=title.strip() or file.filename or "Document",
        description=description,
        file_path=stored.relative_path,
        content_type=file.content_type,
        file_size=len(contents),
        uploaded_by_user_id=user.id,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return DocumentUploadResponse(document=_build_document_read(document))


@router.delete("/files/{document_id}", status_code=204)
def delete_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(*MANAGER_ROLES)),
) -> Response:
    document = db.query(GovernanceDocument).filter(GovernanceDocument.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    storage_service.delete_file(document.file_path)
    db.delete(document)
    db.commit()
    return Response(status_code=204)


@router.get("/files/{document_id}/download")
def download_document(
    document_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    document = (
        db.query(GovernanceDocument)
        .filter(GovernanceDocument.id == document_id)
        .first()
    )
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    stored = storage_service.retrieve_file(document.file_path)
    original_name = document.title or "document"
    filename = original_name if "." in original_name else f"{original_name}.pdf"
    return Response(
        content=stored.content,
        media_type=stored.content_type or document.content_type or "application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
