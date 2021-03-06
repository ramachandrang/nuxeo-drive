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
package org.nuxeo.drive.hierarchy.permission.adapter;

import java.security.Principal;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.adapter.FolderItem;
import org.nuxeo.drive.adapter.impl.AbstractVirtualFolderItem;
import org.nuxeo.drive.service.NuxeoDriveManager;
import org.nuxeo.drive.service.SynchronizationRoots;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.CoreSession;
import org.nuxeo.ecm.core.api.DocumentModel;
import org.nuxeo.ecm.core.api.DocumentSecurityException;
import org.nuxeo.ecm.core.api.IdRef;
import org.nuxeo.runtime.api.Framework;

/**
 * Permission based implementation of the parent {@link FolderItem} of the
 * user's shared synchronization roots.
 *
 * @author Antoine Taillefer
 */
public class SharedSyncRootParentFolderItem extends AbstractVirtualFolderItem {

    private static final long serialVersionUID = 1L;

    private static final Log log = LogFactory.getLog(SharedSyncRootParentFolderItem.class);

    public SharedSyncRootParentFolderItem(String factoryName,
            Principal principal, String parentId, String parentPath,
            String folderName) throws ClientException {
        super(factoryName, principal, parentId, parentPath, folderName);
    }

    protected SharedSyncRootParentFolderItem() {
        // Needed for JSON deserialization
    }

    @Override
    public List<FileSystemItem> getChildren() throws ClientException {

        List<FileSystemItem> children = new ArrayList<FileSystemItem>();
        Map<String, SynchronizationRoots> syncRootsByRepo = Framework.getLocalService(
                NuxeoDriveManager.class).getSynchronizationRoots(principal);
        for (String repositoryName : syncRootsByRepo.keySet()) {
            CoreSession session = getSession(repositoryName);
            Set<IdRef> syncRootRefs = syncRootsByRepo.get(repositoryName).refs;
            Iterator<IdRef> syncRootRefsIt = syncRootRefs.iterator();
            while (syncRootRefsIt.hasNext()) {
                IdRef idRef = syncRootRefsIt.next();
                try {
                    DocumentModel doc = session.getDocument(idRef);
                    // Filter by creator
                    // TODO: allow filtering by dc:creator in
                    // NuxeoDriveManager#getSynchronizationRoots(Principal
                    // principal)
                    if (!session.getPrincipal().getName().equals(
                            doc.getPropertyValue("dc:creator"))) {
                        // TODO: handle null FileSystemItem
                        children.add(getFileSystemItemAdapterService().getFileSystemItem(
                                doc, getId()));
                    }
                } catch (DocumentSecurityException e) {
                    log.debug(String.format(
                            "User %s has no READ access on synchronization root %s, not including it in children.",
                            session.getPrincipal().getName(), idRef));
                }
            }
        }
        Collections.sort(children);
        return children;
    }

}
