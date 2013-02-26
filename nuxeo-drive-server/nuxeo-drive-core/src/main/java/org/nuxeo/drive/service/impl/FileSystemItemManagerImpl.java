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
package org.nuxeo.drive.service.impl;

import java.io.Serializable;
import java.security.Principal;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import javax.transaction.Status;
import javax.transaction.Synchronization;
import javax.transaction.Transaction;

import org.nuxeo.drive.adapter.FileItem;
import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.adapter.FolderItem;
import org.nuxeo.drive.service.FileSystemItemAdapterService;
import org.nuxeo.drive.service.FileSystemItemManager;
import org.nuxeo.ecm.core.api.Blob;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.ClientRuntimeException;
import org.nuxeo.ecm.core.api.CoreInstance;
import org.nuxeo.ecm.core.api.CoreSession;
import org.nuxeo.runtime.api.Framework;
import org.nuxeo.runtime.transaction.TransactionHelper;

/**
 * Default implementation of the {@link FileSystemItemManager}.
 *
 * @author Antoine Taillefer
 */
public class FileSystemItemManagerImpl implements FileSystemItemManager {

    /*------------- Opened sessions against each repository ----------------*/
    protected final ThreadLocal<Map<String, CoreSession>> openedSessions = new ThreadLocal<Map<String, CoreSession>>() {
        @Override
        protected Map<String, CoreSession> initialValue() {
            return new HashMap<String, CoreSession>();
        }
    };

    public CoreSession getSession(String repositoryName, Principal principal)
            throws ClientException {
        final String sessionKey = repositoryName + "/" + principal.getName();
        CoreSession session = openedSessions.get().get(sessionKey);
        if (session == null) {
            Map<String, Serializable> context = new HashMap<String, Serializable>();
            context.put("principal", (Serializable) principal);
            final CoreSession newSession = CoreInstance.getInstance().open(
                    repositoryName, context);
            openedSessions.get().put(sessionKey, newSession);
            try {
                Transaction t = TransactionHelper.lookupTransactionManager().getTransaction();
                if (t == null) {
                    throw new RuntimeException(
                            "FileSystemItemManagerImpl requires an active transaction.");
                }
                t.registerSynchronization(new SessionCloser(newSession,
                        sessionKey));
            } catch (Exception e) {
                throw new ClientRuntimeException(e);
            }
            session = newSession;
        }
        return session;
    }

    protected class SessionCloser implements Synchronization {

        protected final CoreSession session;

        protected final String sessionKey;

        protected SessionCloser(CoreSession session, String sessionKey) {
            this.session = session;
            this.sessionKey = sessionKey;
        }

        @Override
        public void beforeCompletion() {
            CoreInstance.getInstance().close(session);
        }

        @Override
        public void afterCompletion(int status) {
            openedSessions.get().remove(sessionKey);
            if (status != Status.STATUS_COMMITTED) {
                CoreInstance.getInstance().close(session);
            }
        }
    }

    /*------------- Read operations ----------------*/
    @Override
    public List<FileSystemItem> getTopLevelChildren(Principal principal)
            throws ClientException {
        return getTopLevelFolder(principal).getChildren();
    }

    @Override
    public FolderItem getTopLevelFolder(Principal principal)
            throws ClientException {
        return getFileSystemItemAdapterService().getTopLevelFolderItemFactory().getTopLevelFolderItem(
                principal);
    }

    @Override
    public boolean exists(String id, Principal principal)
            throws ClientException {
        return getFileSystemItemAdapterService().getFileSystemItemFactoryForId(
                id).exists(id, principal);
    }

    @Override
    public FileSystemItem getFileSystemItemById(String id, Principal principal)
            throws ClientException {
        return getFileSystemItemAdapterService().getFileSystemItemFactoryForId(
                id).getFileSystemItemById(id, principal);
    }

    @Override
    public List<FileSystemItem> getChildren(String id, Principal principal)
            throws ClientException {
        FileSystemItem fileSystemItem = getFileSystemItemById(id, principal);
        if (!(fileSystemItem instanceof FolderItem)) {
            throw new ClientException(
                    String.format(
                            "Cannot get the children of file system item with id %s because it is not a folder.",
                            id));
        }
        FolderItem folderItem = (FolderItem) fileSystemItem;
        return folderItem.getChildren();
    }

    @Override
    public boolean canMove(String srcId, String destId, Principal principal)
            throws ClientException {
        FileSystemItem srcFsItem = getFileSystemItemById(srcId, principal);
        FileSystemItem destFsItem = getFileSystemItemById(destId, principal);
        if (!(destFsItem instanceof FolderItem)) {
            return false;
        }
        return srcFsItem.canMove((FolderItem) destFsItem);
    }

    /*------------- Write operations ---------------*/
    @Override
    public FolderItem createFolder(String parentId, String name,
            Principal principal) throws ClientException {
        FileSystemItem parentFsItem = getFileSystemItemById(parentId, principal);
        if (!(parentFsItem instanceof FolderItem)) {
            throw new ClientException(
                    String.format(
                            "Cannot create a folder in file system item with id %s because it is not a folder.",
                            parentId));
        }
        FolderItem parentFolder = (FolderItem) parentFsItem;
        return parentFolder.createFolder(name);
    }

    @Override
    public FileItem createFile(String parentId, Blob blob, Principal principal)
            throws ClientException {
        FileSystemItem parentFsItem = getFileSystemItemById(parentId, principal);
        if (!(parentFsItem instanceof FolderItem)) {
            throw new ClientException(
                    String.format(
                            "Cannot create a file in file system item with id %s because it is not a folder.",
                            parentId));
        }
        FolderItem parentFolder = (FolderItem) parentFsItem;
        return parentFolder.createFile(blob);
    }

    @Override
    public FileItem updateFile(String id, Blob blob, Principal principal)
            throws ClientException {
        FileSystemItem fsItem = getFileSystemItemById(id, principal);
        if (!(fsItem instanceof FileItem)) {
            throw new ClientException(
                    String.format(
                            "Cannot update the content of file system item with id %s because it is not a file.",
                            id));
        }
        FileItem file = (FileItem) fsItem;
        file.setBlob(blob);
        return file;
    }

    @Override
    public void delete(String id, Principal principal) throws ClientException {
        FileSystemItem fsItem = getFileSystemItemById(id, principal);
        fsItem.delete();
    }

    @Override
    public FileSystemItem rename(String id, String name, Principal principal)
            throws ClientException {
        FileSystemItem fsItem = getFileSystemItemById(id, principal);
        fsItem.rename(name);
        return fsItem;
    }

    @Override
    public FileSystemItem move(String srcId, String destId, Principal principal)
            throws ClientException {
        FileSystemItem srcFsItem = getFileSystemItemById(srcId, principal);
        FileSystemItem destFsItem = getFileSystemItemById(destId, principal);
        if (!(destFsItem instanceof FolderItem)) {
            throw new ClientException(
                    String.format(
                            "Cannot move a file system item to file system item with id %s because it is not a folder.",
                            destId));
        }
        return srcFsItem.move((FolderItem) destFsItem);
    }

    /*------------- Protected ---------------*/
    protected FileSystemItemAdapterService getFileSystemItemAdapterService() {
        return Framework.getLocalService(FileSystemItemAdapterService.class);
    }

}
