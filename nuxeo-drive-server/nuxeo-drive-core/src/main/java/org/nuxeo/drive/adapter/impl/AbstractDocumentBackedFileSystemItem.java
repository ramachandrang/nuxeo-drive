/*
 * (C) Copyright 2012 Nuxeo SA (http://nuxeo.com/) and contributors.
 *
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the GNU Lesser General Public License
 * (LGPL) version 2.1 which accompanies this distribution, and is available at
 * http://www.gnu.org/licenses/lgpl.html
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * Contributors:
 *     Antoine Taillefer <ataillefer@nuxeo.com>
 */
package org.nuxeo.drive.adapter.impl;

import java.util.ArrayList;
import java.util.Calendar;
import java.util.List;

import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.adapter.FolderItem;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.ClientRuntimeException;
import org.nuxeo.ecm.core.api.CoreSession;
import org.nuxeo.ecm.core.api.DocumentModel;
import org.nuxeo.ecm.core.api.DocumentRef;
import org.nuxeo.ecm.core.api.IdRef;
import org.nuxeo.ecm.core.api.security.SecurityConstants;
import org.nuxeo.ecm.core.trash.TrashService;
import org.nuxeo.runtime.api.Framework;

/**
 * {@link DocumentModel} backed implementation of a {@link FileSystemItem}.
 *
 * @author Antoine Taillefer
 * @see DocumentBackedFileItem
 * @see DocumentBackedFolderItem
 */
public abstract class AbstractDocumentBackedFileSystemItem extends
        AbstractFileSystemItem {

    private static final long serialVersionUID = 1L;

    /** Backing {@link DocumentModel} attributes */
    protected String repositoryName;

    protected String docId;

    protected String docPath;

    protected String docTitle;

    protected AbstractDocumentBackedFileSystemItem(String factoryName,
            DocumentModel doc) throws ClientException {
        this(factoryName, null, doc);
        CoreSession docSession = doc.getCoreSession();
        DocumentModel parentDoc = docSession.getParentDocument(doc.getRef());
        if (parentDoc == null) {
            throw new UnsupportedOperationException(
                    String.format(
                            "Doc %s has no parent document, please provide a FileSystemItem parentId to the constructor.",
                            doc.getPathAsString()));
        } else {
            // Pass a mock parent id when fetching the parent file system item
            // to avoid recursive calls
            this.parentId = getFileSystemItemAdapterService().getFileSystemItem(
                    parentDoc, "mockParentId").getId();
        }
    }

    protected AbstractDocumentBackedFileSystemItem(String factoryName,
            String parentId, DocumentModel doc) throws ClientException {

        super(factoryName, doc.getCoreSession().getPrincipal());

        // Backing DocumentModel attributes
        repositoryName = doc.getRepositoryName();
        docId = doc.getId();
        docPath = doc.getPathAsString();
        docTitle = doc.getTitle();

        // FileSystemItem attributes
        id = computeId(docId);
        this.parentId = parentId;
        creator = (String) doc.getPropertyValue("dc:creator");
        creationDate = (Calendar) doc.getPropertyValue("dc:created");
        lastModificationDate = (Calendar) doc.getPropertyValue("dc:modified");
        CoreSession docSession = doc.getCoreSession();
        canRename = docSession.hasPermission(doc.getRef(),
                SecurityConstants.WRITE_PROPERTIES);
        canDelete = docSession.hasPermission(doc.getRef(),
                SecurityConstants.REMOVE)
                && docSession.hasPermission(doc.getParentRef(),
                        SecurityConstants.REMOVE_CHILDREN);
    }

    protected AbstractDocumentBackedFileSystemItem() {
        // Needed for JSON deserialization
    }

    /*--------------------- FileSystemItem ---------------------*/
    public void delete() throws ClientException {
        List<DocumentModel> docs = new ArrayList<DocumentModel>();
        DocumentModel doc = getDocument(getSession());
        docs.add(doc);
        getTrashService().trashDocuments(docs);
    }

    public boolean canMove(FolderItem dest) throws ClientException {
        // Check source doc deletion
        if (!canDelete) {
            return false;
        }
        // Check add children on destination doc
        AbstractDocumentBackedFileSystemItem docBackedDest = (AbstractDocumentBackedFileSystemItem) dest;
        String destRepoName = docBackedDest.getRepositoryName();
        DocumentRef destDocRef = new IdRef(docBackedDest.getDocId());
        // If source and destination repository are different, use a core
        // session bound to the destination repository
        CoreSession session;
        if (repositoryName.equals(destRepoName)) {
            session = getSession();
        } else {
            session = getSession(destRepoName);
        }
        if (!session.hasPermission(destDocRef, SecurityConstants.ADD_CHILDREN)) {
            return false;
        }
        return true;
    }

    public FileSystemItem move(FolderItem dest) throws ClientException {
        DocumentRef sourceDocRef = new IdRef(docId);
        AbstractDocumentBackedFileSystemItem docBackedDest = (AbstractDocumentBackedFileSystemItem) dest;
        String destRepoName = docBackedDest.getRepositoryName();
        DocumentRef destDocRef = new IdRef(docBackedDest.getDocId());
        // If source and destination repository are different, delete source and
        // create doc in destination
        if (repositoryName.equals(destRepoName)) {
            CoreSession session = getSession();
            DocumentModel movedDoc = session.move(sourceDocRef, destDocRef,
                    null);
            session.save();
            return getFileSystemItemAdapterService().getFileSystemItem(
                    movedDoc, dest.getId());
        } else {
            // TODO: implement move to another repository
            throw new UnsupportedOperationException(
                    "Multi repository move is not supported yet.");
        }
    }

    /*--------------------- Protected -------------------------*/
    protected CoreSession getSession() throws ClientException {
        return getSession(repositoryName);
    }

    protected String computeId(String docId) {
        StringBuilder sb = new StringBuilder();
        sb.append(super.getId());
        sb.append(repositoryName);
        sb.append("/");
        sb.append(docId);
        return sb.toString();
    }

    protected String getRepositoryName() {
        return repositoryName;
    }

    protected String getDocId() {
        return docId;
    }

    protected String getDocPath() {
        return docPath;
    }

    protected DocumentModel getDocument(CoreSession session)
            throws ClientException {
        return session.getDocument(new IdRef(docId));
    }

    protected void updateLastModificationDate(DocumentModel doc)
            throws ClientException {
        lastModificationDate = (Calendar) doc.getPropertyValue("dc:modified");
    }

    protected TrashService getTrashService() {
        return Framework.getLocalService(TrashService.class);
    }

    /*---------- Needed for JSON deserialization ----------*/
    @Override
    protected void setId(String id) {
        try {
            super.setId(id);
            String[] idFragments = parseFileSystemId(id);
            this.factoryName = idFragments[0];
            this.repositoryName = idFragments[1];
            this.docId = idFragments[2];

        } catch (ClientException e) {
            throw new ClientRuntimeException(
                    "Cannot set id as it cannot be parsed.", e);
        }

    }

    protected String[] parseFileSystemId(String id) throws ClientException {

        // Parse id, expecting pattern:
        // fileSystemItemFactoryName/repositoryName/docId
        String[] idFragments = id.split("/");
        if (idFragments.length != 3) {
            throw new ClientException(
                    String.format(
                            "FileSystemItem id %s is not valid. Should match the 'fileSystemItemFactoryName/repositoryName/docId' pattern.",
                            id));
        }
        return idFragments;
    }

}
