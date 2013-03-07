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
package org.nuxeo.drive.service;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

import java.lang.reflect.Field;
import java.lang.reflect.InvocationHandler;
import java.lang.reflect.Proxy;
import java.security.Principal;
import java.util.Calendar;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.junit.runner.RunWith;
import org.nuxeo.drive.service.impl.AuditChangeFinder;
import org.nuxeo.drive.service.impl.FileSystemChangeSummary;
import org.nuxeo.drive.service.impl.FileSystemItemChange;
import org.nuxeo.drive.service.impl.RootDefinitionsHelper;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.CoreSession;
import org.nuxeo.ecm.core.api.DocumentModel;
import org.nuxeo.ecm.core.api.IdRef;
import org.nuxeo.ecm.core.api.TransactionalCoreSessionWrapper;
import org.nuxeo.ecm.core.api.impl.blob.StringBlob;
import org.nuxeo.ecm.core.api.local.LocalSession;
import org.nuxeo.ecm.core.event.EventService;
import org.nuxeo.ecm.core.event.EventServiceAdmin;
import org.nuxeo.ecm.core.test.annotations.TransactionalConfig;
import org.nuxeo.ecm.platform.audit.AuditFeature;
import org.nuxeo.ecm.platform.usermanager.NuxeoPrincipalImpl;
import org.nuxeo.runtime.api.Framework;
import org.nuxeo.runtime.test.runner.Deploy;
import org.nuxeo.runtime.test.runner.Features;
import org.nuxeo.runtime.test.runner.FeaturesRunner;
import org.nuxeo.runtime.test.runner.LocalDeploy;
import org.nuxeo.runtime.transaction.TransactionHelper;

import com.google.inject.Inject;

/**
 * Test the {@link AuditChangeFinder}.
 */
@RunWith(FeaturesRunner.class)
@Features(AuditFeature.class)
// We handle transaction start and commit manually to make it possible to have
// several consecutive transactions in a test method
@TransactionalConfig(autoStart = false)
@Deploy("org.nuxeo.drive.core")
@LocalDeploy("org.nuxeo.drive.core:OSGI-INF/test-nuxeodrive-types-contrib.xml")
public class TestAuditFileSystemChangeFinder {

    @Inject
    protected CoreSession session;

    @Inject
    protected EventService eventService;

    @Inject
    protected NuxeoDriveManager nuxeoDriveManager;

    @Inject
    protected EventServiceAdmin eventServiceAdmin;

    protected long lastSuccessfulSync;

    protected String lastSyncActiveRootDefinitions;

    protected DocumentModel folder1;

    protected DocumentModel folder2;

    @Before
    public void init() throws Exception {
        // Enable deletion listener because the tear down disables it
        eventServiceAdmin.setListenerEnabledFlag(
                "nuxeoDriveFileSystemDeletionListener", true);

        lastSuccessfulSync = Calendar.getInstance().getTimeInMillis();
        lastSyncActiveRootDefinitions = "";
        Framework.getProperties().put("org.nuxeo.drive.document.change.limit",
                "10");

        dispose(session);
        TransactionHelper.startTransaction();
        folder1 = session.createDocument(session.createDocumentModel("/",
                "folder1", "Folder"));
        folder2 = session.createDocument(session.createDocumentModel("/",
                "folder2", "Folder"));
        session.createDocument(session.createDocumentModel("/", "folder3",
                "Folder"));
        commitAndWaitForAsyncCompletion();
    }

    @After
    public void tearDown() {
        // Disable deletion listener for the repository cleanup phase done in
        // CoreFeature#afterTeardown to avoid exception due to no active
        // transaction in FileSystemItemManagerImpl#getSession
        eventServiceAdmin.setListenerEnabledFlag(
                "nuxeoDriveFileSystemDeletionListener", false);
    }

    @Test
    public void testFindChanges() throws Exception {
        TransactionHelper.startTransaction();
        // No sync roots
        List<FileSystemItemChange> changes = getChanges();
        assertNotNull(changes);
        assertTrue(changes.isEmpty());

        // Sync roots but no changes
        nuxeoDriveManager.registerSynchronizationRoot(
                session.getPrincipal().getName(), folder1, session);
        nuxeoDriveManager.registerSynchronizationRoot(
                session.getPrincipal().getName(), folder2, session);
        changes = getChanges();
        assertTrue(changes.isEmpty());

        // Create 3 documents, only 2 in sync roots
        DocumentModel doc1 = session.createDocumentModel("/folder1", "doc1",
                "File");
        doc1.setPropertyValue("file:content", new StringBlob(
                "The content of file 1."));
        doc1 = session.createDocument(doc1);
        Thread.sleep(1000);
        DocumentModel doc2 = session.createDocumentModel("/folder2", "doc2",
                "File");
        doc2.setPropertyValue("file:content", new StringBlob(
                "The content of file 2."));
        doc2 = session.createDocument(doc2);
        DocumentModel doc3 = session.createDocumentModel("/folder3", "doc3",
                "File");
        doc3.setPropertyValue("file:content", new StringBlob(
                "The content of file 3."));
        doc3 = session.createDocument(doc3);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changes = getChanges();
        assertEquals(2, changes.size());
        FileSystemItemChange change = changes.get(0);
        assertEquals("test", change.getRepositoryId());
        assertEquals("documentCreated", change.getEventId());
        assertEquals(doc2.getId(), change.getDocUuid());
        change = changes.get(1);
        assertEquals("test", change.getRepositoryId());
        assertEquals("documentCreated", change.getEventId());
        assertEquals(doc1.getId(), change.getDocUuid());

        // No changes since last successful sync
        changes = getChanges();
        assertTrue(changes.isEmpty());

        // Update both synchronized documents and unsynchronize a root
        doc1.setPropertyValue("file:content", new StringBlob(
                "The content of file 1, updated."));
        session.saveDocument(doc1);
        doc2.setPropertyValue("file:content", new StringBlob(
                "The content of file 2, updated."));
        session.saveDocument(doc2);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        nuxeoDriveManager.unregisterSynchronizationRoot(
                session.getPrincipal().getName(), folder2, session);
        changes = getChanges();
        assertEquals(2, changes.size());
        // the root unregistration is mapped to a fake deletion from the
        // client's
        // point of view
        change = changes.get(0);
        assertEquals("test", change.getRepositoryId());
        assertEquals("deleted", change.getEventId());
        assertEquals(folder2.getId(), change.getDocUuid());

        change = changes.get(1);
        assertEquals("test", change.getRepositoryId());
        assertEquals("documentModified", change.getEventId());
        assertEquals(doc1.getId(), change.getDocUuid());

        // Delete a document with a lifecycle transition (trash)
        session.followTransition(doc1.getRef(), "delete");
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changes = getChanges();
        assertEquals(1, changes.size());
        change = changes.get(0);
        assertEquals("test", change.getRepositoryId());
        assertEquals("deleted", change.getEventId());
        assertEquals(doc1.getId(), change.getDocUuid());
        assertEquals("defaultFileSystemItemFactory#test#" + doc1.getId(),
                change.getFileSystemItemId());

        // Restore a deleted document and move a document in a newly
        // synchronized root
        session.followTransition(doc1.getRef(), "undelete");
        Thread.sleep(1000);
        session.move(doc3.getRef(), folder2.getRef(), null);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        nuxeoDriveManager.registerSynchronizationRoot(
                session.getPrincipal().getName(), folder2, session);
        changes = getChanges();
        assertEquals(2, changes.size());
        change = changes.get(0);
        assertEquals("test", change.getRepositoryId());
        assertEquals("documentMoved", change.getEventId());
        assertEquals(doc3.getId(), change.getDocUuid());
        change = changes.get(1);
        assertEquals("test", change.getRepositoryId());
        assertEquals("lifecycle_transition_event", change.getEventId());
        assertEquals(doc1.getId(), change.getDocUuid());

        // Physical deletion without triggering the delete transition first
        session.removeDocument(doc3.getRef());
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changes = getChanges();
        assertEquals(1, changes.size());
        change = changes.get(0);
        assertEquals("test", change.getRepositoryId());
        assertEquals("deleted", change.getEventId());
        assertEquals(doc3.getId(), change.getDocUuid());
        assertEquals("defaultFileSystemItemFactory#test#" + doc3.getId(),
                change.getFileSystemItemId());

        // Too many changes
        session.followTransition(doc1.getRef(), "delete");
        session.followTransition(doc2.getRef(), "delete");
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        Framework.getProperties().put("org.nuxeo.drive.document.change.limit",
                "1");
        FileSystemChangeSummary changeSummary = getChangeSummary(session.getPrincipal());
        assertEquals(true, changeSummary.getHasTooManyChanges());
        TransactionHelper.commitOrRollbackTransaction();
    }

    @Test
    public void testGetChangeSummary() throws Exception {
        TransactionHelper.startTransaction();
        Principal admin = new NuxeoPrincipalImpl("Administrator");

        // No sync roots => shouldn't find any changes
        FileSystemChangeSummary changeSummary = getChangeSummary(admin);
        assertNotNull(changeSummary);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Register sync roots => should find changes: the newly
        // synchronized root folders as they are updated by the synchronization
        // registration process
        nuxeoDriveManager.registerSynchronizationRoot(admin.getName(), folder1,
                session);
        nuxeoDriveManager.registerSynchronizationRoot(admin.getName(), folder2,
                session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changeSummary = getChangeSummary(admin);
        assertEquals(2, changeSummary.getFileSystemChanges().size());
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Create 3 documents, only 2 in sync roots => should find 2 changes
        TransactionHelper.commitOrRollbackTransaction();
        TransactionHelper.startTransaction();
        DocumentModel doc1 = session.createDocumentModel("/folder1", "doc1",
                "File");
        doc1.setPropertyValue("file:content", new StringBlob(
                "The content of file 1."));
        doc1 = session.createDocument(doc1);
        Thread.sleep(1000);
        DocumentModel doc2 = session.createDocumentModel("/folder2", "doc2",
                "File");
        doc2.setPropertyValue("file:content", new StringBlob(
                "The content of file 2."));
        doc2 = session.createDocument(doc2);
        session.createDocument(session.createDocumentModel("/folder3", "doc3",
                "File"));
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changeSummary = getChangeSummary(admin);

        List<FileSystemItemChange> changes = changeSummary.getFileSystemChanges();
        assertEquals(2, changes.size());
        FileSystemItemChange docChange = changes.get(0);
        assertEquals("test", docChange.getRepositoryId());
        assertEquals("documentCreated", docChange.getEventId());
        assertEquals(
                "project",
                session.getDocument(new IdRef(docChange.getDocUuid())).getCurrentLifeCycleState());
        assertEquals(doc2.getId(), docChange.getDocUuid());
        docChange = changes.get(1);
        assertEquals("test", docChange.getRepositoryId());
        assertEquals("documentCreated", docChange.getEventId());
        assertEquals(
                "project",
                session.getDocument(new IdRef(docChange.getDocUuid())).getCurrentLifeCycleState());
        assertEquals(doc1.getId(), docChange.getDocUuid());

        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Create a document that should not be synchronized because not
        // adaptable as a FileSystemItem (not Folderish nor a BlobHolder with a
        // blob) => should not be considered as a change
        session.createDocument(session.createDocumentModel("/folder1",
                "notSynchronizableDoc", "NotSynchronizable"));
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changeSummary = getChangeSummary(admin);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Create 2 documents in the same sync root: "/folder1" and 1 document
        // in another sync root => should find 2 changes for "/folder1"
        DocumentModel doc3 = session.createDocumentModel("/folder1", "doc3",
                "File");
        doc3.setPropertyValue("file:content", new StringBlob(
                "The content of file 3."));
        doc3 = session.createDocument(doc3);
        DocumentModel doc4 = session.createDocumentModel("/folder1", "doc4",
                "File");
        doc4.setPropertyValue("file:content", new StringBlob(
                "The content of file 4."));
        doc4 = session.createDocument(doc4);
        DocumentModel doc5 = session.createDocumentModel("/folder2", "doc5",
                "File");
        doc5.setPropertyValue("file:content", new StringBlob(
                "The content of file 5."));
        doc5 = session.createDocument(doc5);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        changeSummary = getChangeSummary(admin);
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());
        assertEquals(3, changeSummary.getFileSystemChanges().size());

        // No changes since last successful sync
        changeSummary = getChangeSummary(admin);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Test too many changes
        session.followTransition(doc1.getRef(), "delete");
        session.followTransition(doc2.getRef(), "delete");
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        Framework.getProperties().put("org.nuxeo.drive.document.change.limit",
                "1");
        changeSummary = getChangeSummary(admin);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertEquals(Boolean.TRUE, changeSummary.getHasTooManyChanges());
        TransactionHelper.commitOrRollbackTransaction();
    }

    @Test
    public void testGetChangeSummaryOnRootDocuments() throws Exception {
        TransactionHelper.startTransaction();
        Principal admin = new NuxeoPrincipalImpl("Administrator");
        Principal otherUser = new NuxeoPrincipalImpl("some-other-user");

        // No root registered by default: no changes
        Set<IdRef> activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertTrue(activeRootRefs.isEmpty());

        FileSystemChangeSummary changeSummary = getChangeSummary(admin);
        assertNotNull(changeSummary);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertEquals(Boolean.FALSE, changeSummary.getHasTooManyChanges());

        // Register a root for someone else
        nuxeoDriveManager.registerSynchronizationRoot(otherUser.getName(),
                folder1, session);

        // Administrator does not see any change
        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertTrue(activeRootRefs.isEmpty());

        changeSummary = getChangeSummary(admin);
        assertNotNull(changeSummary);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertFalse(changeSummary.getHasTooManyChanges());

        // Register a new sync root
        nuxeoDriveManager.registerSynchronizationRoot(admin.getName(), folder1,
                session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertEquals(1, activeRootRefs.size());
        assertEquals(folder1.getRef(), activeRootRefs.iterator().next());

        // The new sync root is detected in the change summary
        changeSummary = getChangeSummary(admin);
        assertNotNull(changeSummary);

        List<FileSystemItemChange> changes = changeSummary.getFileSystemChanges();
        assertEquals(1, changes.size());
        FileSystemItemChange fsItemChange = changes.get(0);
        // TODO: this should be detected has a file system item
        // creation rather than modification
        assertEquals("documentModified", fsItemChange.getEventId());
        assertEquals(
                "defaultSyncRootFolderItemFactory#test#" + folder1.getId(),
                fsItemChange.getFileSystemItem().getId());

        // Check that root unregistration is detected as a deletion
        nuxeoDriveManager.unregisterSynchronizationRoot(admin.getName(),
                folder1, session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();

        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertTrue(activeRootRefs.isEmpty());
        changeSummary = getChangeSummary(admin);
        changes = changeSummary.getFileSystemChanges();
        assertEquals(1, changes.size());
        fsItemChange = changes.get(0);
        assertEquals("deleted", fsItemChange.getEventId());
        assertEquals(
                "defaultSyncRootFolderItemFactory#test#" + folder1.getId(),
                fsItemChange.getFileSystemItemId());

        // Register back the root, it's activity is again detected by the client
        nuxeoDriveManager.registerSynchronizationRoot(admin.getName(), folder1,
                session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();
        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertEquals(activeRootRefs.size(), 1);

        changeSummary = getChangeSummary(admin);
        changes = changeSummary.getFileSystemChanges();
        assertEquals(1, changes.size());
        fsItemChange = changes.get(0);
        // TODO: this should be detected has a file system item
        // creation rather than modification
        assertEquals("documentModified", fsItemChange.getEventId());
        assertEquals(
                "defaultSyncRootFolderItemFactory#test#" + folder1.getId(),
                fsItemChange.getFileSystemItem().getId());

        // Test deletion of a root
        session.followTransition(folder1.getRef(), "delete");
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();
        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertTrue(activeRootRefs.isEmpty());

        // The root is no longer active
        activeRootRefs = nuxeoDriveManager.getSynchronizationRootReferences(session);
        assertNotNull(activeRootRefs);
        assertTrue(activeRootRefs.isEmpty());

        // The deletion of the root itself is mapped as filesystem
        // deletion event
        changeSummary = getChangeSummary(admin);
        changes = changeSummary.getFileSystemChanges();
        assertEquals(1, changes.size());
        fsItemChange = changes.get(0);
        assertEquals("deleted", fsItemChange.getEventId());
        assertEquals(
                "defaultSyncRootFolderItemFactory#test#" + folder1.getId(),
                fsItemChange.getFileSystemItemId());

        commitAndWaitForAsyncCompletion();
    }

    @Test
    public void testGetChangeSummaryOnRootDocumentsNullChange()
            throws Exception {
        // check that consecutive root registration + unregistration do not lead
        // to a visible change for the client.
        TransactionHelper.startTransaction();
        Principal someUser = new NuxeoPrincipalImpl("some-user");
        nuxeoDriveManager.registerSynchronizationRoot(someUser.getName(),
                folder1, session);
        nuxeoDriveManager.unregisterSynchronizationRoot(someUser.getName(),
                folder1, session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();
        FileSystemChangeSummary changeSummary = getChangeSummary(someUser);
        assertNotNull(changeSummary);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertFalse(changeSummary.getHasTooManyChanges());

        // Do it a second time to check that the client did not receive bad
        // active root markers
        nuxeoDriveManager.registerSynchronizationRoot(someUser.getName(),
                folder1, session);
        nuxeoDriveManager.unregisterSynchronizationRoot(someUser.getName(),
                folder1, session);
        commitAndWaitForAsyncCompletion();
        TransactionHelper.startTransaction();
        changeSummary = getChangeSummary(someUser);
        assertNotNull(changeSummary);
        assertTrue(changeSummary.getFileSystemChanges().isEmpty());
        assertFalse(changeSummary.getHasTooManyChanges());
        commitAndWaitForAsyncCompletion();
    }

    /**
     * Gets the document changes using the {@link AuditChangeFinder} and updates
     * the {@link #lastSuccessfulSync} date.
     *
     * @throws ClientException
     */
    protected List<FileSystemItemChange> getChanges()
            throws InterruptedException, ClientException {
        return getChangeSummary(session.getPrincipal()).getFileSystemChanges();
    }

    /**
     * Gets the document changes summary for the given user's synchronization
     * roots using the {@link NuxeoDriveManager} and updates the
     * {@link #lastSuccessfulSync} date.
     */
    protected FileSystemChangeSummary getChangeSummary(Principal principal)
            throws ClientException, InterruptedException {
        // Wait 1 second as the audit change finder relies on steps of 1 second
        Thread.sleep(1000);
        Map<String, Set<IdRef>> lastSyncActiveRootRefs = RootDefinitionsHelper.parseRootDefinitions(lastSyncActiveRootDefinitions);
        FileSystemChangeSummary changeSummary = nuxeoDriveManager.getChangeSummary(
                principal, lastSyncActiveRootRefs, lastSuccessfulSync);
        assertNotNull(changeSummary);
        lastSuccessfulSync = changeSummary.getSyncDate();
        lastSyncActiveRootDefinitions = changeSummary.getActiveSynchronizationRootDefinitions();
        return changeSummary;
    }

    protected void commitAndWaitForAsyncCompletion() throws Exception {
        TransactionHelper.commitOrRollbackTransaction();
        dispose(session);
        eventService.waitForAsyncCompletion();
    }

    protected void dispose(CoreSession session) throws Exception {
        if (Proxy.isProxyClass(session.getClass())) {
            InvocationHandler handler = Proxy.getInvocationHandler(session);
            if (handler instanceof TransactionalCoreSessionWrapper) {
                Field field = TransactionalCoreSessionWrapper.class.getDeclaredField("session");
                field.setAccessible(true);
                session = (CoreSession) field.get(handler);
            }
        }
        if (!(session instanceof LocalSession)) {
            throw new UnsupportedOperationException(
                    "Cannot dispose session of class " + session.getClass());
        }
        ((LocalSession) session).getSession().dispose();
    }
}
